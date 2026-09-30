"""Parse IB (保險業公開資訊觀測站) per-product detail pages
(property5-1-{1..5}.aspx).

Verified live (2026-09-13) against 臺灣產物保險股份有限公司 products. All five
pages share the same underlying markup: a disclosure table of
`<tr><td>label</td><td>value</td></tr>` rows (header row
法定揭露項目/揭露內容, or occasionally a page-specific pair like
條款項目/保險契約條款內容), where `label` is one of a small known set and
`value` is either inline text, a nested `<table>` (structured data), or an
ASP.NET LinkButton (`javascript:__doPostBack('ctl00$MainContent$LinkButtonN','')`)
naming a file with no resolvable static URL -- see document_parser.py's
module docstring for why that's recorded with `url=""` rather than guessed.

Function-number -> page meaning (confirmed via the real product list's own
<select> options, reproduced in property_parser.py's FUNCTION_OPTIONS):
    1 基本資訊                                          -- _parse_basic_info
    2 條款內容                                           -- _parse_policy_terms
    3 短期費率表                                         -- _parse_short_term_rate_table
    4 銷售予金融消費者之保險商品預定附加費用率與保費退費係數表  -- _parse_fees_and_rebate
    5 理賠申請文件及程序                                   -- _parse_claim_info

Not every function has data for every product -- verified two different
outcomes for "no data" on the same function (3, 短期費率表):
    - an explicit table row reading "本商品不適用短期費率" (stays on the
      detail page -- handled as ordinary text, no special-casing needed), and
    - a bounce back to the company's own Property_Layout.aspx search page
      (no error, just nothing to show). This second case is detected by the
      presence of that search page's own `txtProductCode` input field, and
      reported as status="redirected_to_search" -- distinctly enough from
      TII's DetailList.aspx CAPTCHA-avoidance redirect (see
      scripts/sources/tii/README.md) since here it's an internal analytics
      bounce, not a rejection.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from document_parser import extract_documents, extract_linkbutton_documents  # noqa: E402
from source import DocumentType, IbDocumentLink  # noqa: E402


# Verified live 2026-09-14: several products' function-2 (條款內容) page is
# JUST this one row -- label="條款項目", value="保險契約條款內容" -- with no
# actual document/text row beneath it. That's the disclosure table's own
# column-header rendered as an ordinary <tr><td>label</td><td>value</td></tr>
# (see this module's own top docstring, which already flagged this
# ambiguity before there was a concrete case of it mattering: nothing here
# previously depended on distinguishing a header row from a real one,
# because a real document/text row's presence just overwrote whatever an
# earlier row -- header included -- had set). It started mattering with
# scripts/resolve_ib_product_details.py's inline-text extraction: without
# this filter, a product with genuinely nothing on this page for this
# function would get a fabricated "document" whose entire content is the
# table's own header text ("保險契約條款內容" / "內容"), not real
# disclosure content. Matched on the LABEL (structural, not
# product-specific) rather than guessing from the value text, since the
# value text varies by function ("保險契約條款內容" for 條款項目 but plain
# "內容" for at least one other function) while these two labels don't.
_HEADER_ROW_LABELS = {"法定揭露項目", "條款項目"}


def _is_redirected_to_search(soup: BeautifulSoup) -> bool:
    """True if this response is actually the company search page (a bounce
    for "nothing to show for this function"), not the detail page we asked
    for. Keyed on the search form's own input name -- distinctive and
    confirmed present only on Property_Layout.aspx.
    """
    return soup.find("input", attrs={"name": "ctl00$MainContent$txtProductCode"}) is not None


def _label_value_rows(soup: BeautifulSoup) -> list[tuple[str, Any]]:
    """(label_text, value_cell_tag) for every 2-cell disclosure table row.

    Keeps the value as its BeautifulSoup tag (not just text) so callers can
    tell inline text apart from a nested <table> or a LinkButton -- collapsing
    to text too early would lose that distinction.
    """
    pairs = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        if label and label not in _HEADER_ROW_LABELS:
            pairs.append((label, cells[1]))
    return pairs


def _value_cell_documents(value_cell, base_url: str) -> list[IbDocumentLink]:
    docs = extract_linkbutton_documents(str(value_cell))
    docs += extract_documents(str(value_cell), base_url=base_url)
    return docs


def _value_cell_table(value_cell) -> list[list[str]] | None:
    """A nested <table>'s rows as plain text, if the value cell has one
    (e.g. function 4's per-channel commission-rate breakdown). Returns None
    if there's no nested table -- distinct from an empty list, so callers
    don't confuse "no table here" with "table with zero rows".
    """
    nested = value_cell.find("table")
    if nested is None:
        return None
    return [[cell.get_text(strip=True) for cell in row.find_all("td")] for row in nested.find_all("tr")]


def _parse_basic_info(soup: BeautifulSoup) -> dict[str, Any]:
    fields: dict[str, str] = {}
    raw: dict[str, str] = {}
    for label, value_cell in _label_value_rows(soup):
        text = value_cell.get_text(strip=True)
        raw[label] = text
        if "商品代碼" in label:
            fields["product_code"] = text
        elif "商品名稱" in label:
            fields["product_name"] = text
        elif label == "險別":
            fields["insurance_type"] = text
        elif "初次送審" in label and "日期" in label:
            fields["approval_date"] = text
        elif "初次送審" in label and "文號" in label:
            fields["approval_number"] = text
        elif "最近一次" in label and "核准" in label and "日期" in label:
            fields["latest_approval_date"] = text
        elif "最近一次" in label and "核准" in label and "文號" in label:
            fields["latest_approval_number"] = text
        elif "最近一次檢送保險商品資料庫" in label and "日期" in label:
            fields["last_sent_to_tii_date"] = text
        elif "最近一次檢送保險商品資料庫" in label and "文號" in label:
            fields["last_sent_to_tii_number"] = text
    return {"fields": fields, "raw_label_values": raw}


def _parse_policy_terms(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    raw: dict[str, str] = {}
    documents: list[IbDocumentLink] = []
    inline_text = ""
    for label, value_cell in _label_value_rows(soup):
        raw[label] = value_cell.get_text(strip=True)
        if "商品代碼" in label or "商品名稱" in label:
            continue
        cell_docs = _value_cell_documents(value_cell, base_url)
        if cell_docs:
            for doc in cell_docs:
                doc.document_type = DocumentType.POLICY_TERMS
            documents.extend(cell_docs)
        else:
            text = value_cell.get_text(strip=True)
            if text:
                inline_text = text
    return {"raw_label_values": raw, "inline_text": inline_text, "documents": documents}


def _parse_short_term_rate_table(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    raw: dict[str, str] = {}
    documents: list[IbDocumentLink] = []
    table: list[list[str]] | None = None
    inline_text = ""
    for label, value_cell in _label_value_rows(soup):
        raw[label] = value_cell.get_text(strip=True)
        if "商品代碼" in label or "商品名稱" in label:
            continue
        nested_table = _value_cell_table(value_cell)
        if nested_table is not None:
            table = nested_table
            continue
        cell_docs = _value_cell_documents(value_cell, base_url)
        if cell_docs:
            for doc in cell_docs:
                doc.document_type = DocumentType.SHORT_TERM_RATE_TABLE
            documents.extend(cell_docs)
        else:
            text = value_cell.get_text(strip=True)
            if text:
                inline_text = text  # e.g. "本商品不適用短期費率"
    return {"raw_label_values": raw, "inline_text": inline_text, "table": table, "documents": documents}


def _parse_fees_and_rebate(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    raw: dict[str, str] = {}
    documents: list[IbDocumentLink] = []
    channel_rate_table: list[list[str]] | None = None
    for label, value_cell in _label_value_rows(soup):
        raw[label] = value_cell.get_text(strip=True)
        if "商品代碼" in label or "商品名稱" in label:
            continue

        nested_table = _value_cell_table(value_cell)
        if nested_table is not None:
            channel_rate_table = nested_table

        cell_docs = _value_cell_documents(value_cell, base_url)
        for doc in cell_docs:
            if "退費" in label:
                doc.document_type = DocumentType.RATE_TABLE
            else:
                doc.document_type = DocumentType.COMMISSION_AND_EXPENSE_TABLE
        documents.extend(cell_docs)

    return {"raw_label_values": raw, "channel_rate_table": channel_rate_table, "documents": documents}


def _parse_claim_info(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    raw: dict[str, str] = {}
    documents: list[IbDocumentLink] = []
    claim_document_text = ""
    for label, value_cell in _label_value_rows(soup):
        raw[label] = value_cell.get_text(strip=True)
        if "商品代碼" in label or "商品名稱" in label:
            continue

        cell_docs = _value_cell_documents(value_cell, base_url)
        if "文件" in label and not cell_docs:
            text = value_cell.get_text(strip=True)
            if text:
                claim_document_text = text
        for doc in cell_docs:
            doc.document_type = DocumentType.CLAIM_PROCEDURE if "程序" in label else DocumentType.CLAIM_DOCUMENT
        documents.extend(cell_docs)

    return {"raw_label_values": raw, "claim_document_text": claim_document_text, "documents": documents}


_FUNCTION_PARSERS = {
    1: lambda soup, base_url: _parse_basic_info(soup),
    2: _parse_policy_terms,
    3: _parse_short_term_rate_table,
    4: _parse_fees_and_rebate,
    5: _parse_claim_info,
}


def parse_detail_page(html: str, function_number: int, page_url: str) -> dict[str, Any]:
    """Parse one property5-1-N.aspx page. Returns at least {"status", ...}.

    status is one of:
      "redirected_to_search" -- bounced to the company search page, nothing
                                 to show for this function on this product
      "ok"                    -- parsed successfully (may still have little
                                 data -- e.g. an explicit "not applicable"
                                 table row is status="ok", not an error)
    """
    soup = BeautifulSoup(html, "html.parser")
    if _is_redirected_to_search(soup):
        return {"status": "redirected_to_search", "function_number": function_number}

    parser = _FUNCTION_PARSERS.get(function_number)
    if parser is None:
        return {"status": "unknown_function", "function_number": function_number}

    result = parser(soup, page_url)
    result["status"] = "ok"
    result["function_number"] = function_number
    return result
