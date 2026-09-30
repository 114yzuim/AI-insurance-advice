"""Parse a TII ResultQueryAll.aspx full-index list page.

`ResultQueryAll.aspx?page=N` is a public, non-CAPTCHA-gated paginated index
of every product in TII's database -- verified live (2026-09-13): fetching
page=1 with no query parameters beyond `page` returned 195,255 total
records, no auth, no CAPTCHA. This is a different page from `Query.aspx`
(the CAPTCHA-gated search form -- still off-limits) and `DetailList.aspx`
(per-product detail, handled by detail_parser.py, not this module). See
scripts/sources/tii/README.md for how these fit together.

The page exposes only three columns per product: 保險商品名稱 (a link to
`DetailList.aspx?productId=...`, i.e. the product name -- with no separate
company-name column), 銷售日 (sale start date), and 停售日 (sale end date, or
the literal text "未停售" meaning "not yet discontinued" rather than a
date). Nothing else -- company, product code, insurance category/type,
approval date/number -- is present on this page, so all of those come out
empty here; they need DetailList.aspx (Phase 1's ingest_tii_product.py) or a
company-site adapter.

company_name is deliberately left blank for every record. Some product-name
strings on this page happen to start with a recognizable company name (e.g.
"臺灣產物貨物運輸保險"), but plenty don't (e.g. "Hermes Asia Pacific
Limited.-87TB5199 -2022" -- a coinsurance/open-cover policy name with no
company prefix at all), and there is no reliable, non-guessing way to split
"company" from "product name" out of one free-text string. Leaving it blank
is the conservative choice this module commits to; note that
reconcile_source_records.py currently skips any record with an empty
company_name, so these records will need a company_name filled in (from a
detail-page fetch or another source) before Phase 3 will fold them into a
product_family.

parse_result_page() is built against a REAL captured page (see
fixtures/real_result_page_1.html's header comment), not a guess.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

DETAIL_LINK_RE = re.compile(r"DetailList\.aspx\?productId=([^&#]+)", re.I)
_TOTAL_RECORDS_RE = re.compile(r"總共找到\s*([\d,]+)\s*筆")
# ROC-style dd/dd/dd-ish date, e.g. "108/07/25" or "037/03/12". Anything that
# doesn't look like this (notably the literal status text "未停售") is left
# out of the structured date field rather than guessed at.
_DATE_SHAPE_RE = re.compile(r"^\d{2,3}/\d{2}/\d{2}$")


def _as_date_or_blank(text: str) -> str:
    text = (text or "").strip()
    return text if _DATE_SHAPE_RE.match(text) else ""


def _extract_total_records(soup: BeautifulSoup) -> int | None:
    match = _TOTAL_RECORDS_RE.search(soup.get_text())
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _extract_page_size(soup: BeautifulSoup) -> int | None:
    """Read the selected value of the "每頁顯示" <select name="PageCrt">.

    Used only to derive total_pages; if TII ever changes this control's
    markup, we simply stop reporting total_pages rather than guessing a
    page size.
    """
    select = soup.find("select", attrs={"name": "PageCrt"})
    if select is None:
        return None
    selected = select.find("option", selected=True) or select.find("option")
    if selected is None or not selected.get("value"):
        return None
    try:
        return int(selected["value"])
    except ValueError:
        return None


def _extract_current_page(page_url: str) -> int:
    """Current page number, read from the `page=` query param on `page_url`
    itself (always available to the caller) rather than by guessing which
    pagination link's markup means "this is the active one".
    """
    query = parse_qs(urlsplit(page_url).query)
    values = query.get("page")
    if not values:
        return 1
    try:
        return int(values[0])
    except ValueError:
        return 1


def _extract_header_labels(soup: BeautifulSoup) -> list[str]:
    """Column header text, e.g. ["保險商品名稱", "銷售日", "停售日"].

    TII renders these as `<font color="#333333">label</font>` cells in the
    header row. Used only to build human-readable raw_fields keys; if this
    selector stops matching, callers fall back to generic column_N keys.
    """
    return [text for font in soup.find_all("font", attrs={"color": "#333333"}) if (text := font.get_text(strip=True))]


def parse_result_page(html: str, page_url: str) -> dict[str, Any]:
    """Parse one ResultQueryAll.aspx page.

    Returns {"total_records", "current_page", "total_pages", "records"}.
    Every record is a plain dict shaped like the other TII source records in
    this package (see scripts/sources/tii/source.py's SourceProductRecord),
    with unavailable fields left as "" rather than guessed at, and an empty
    `documents` list (this page has no attachment links -- see
    document_parser.py for that, applied to DetailList.aspx instead).
    """
    soup = BeautifulSoup(html, "html.parser")

    total_records = _extract_total_records(soup)
    page_size = _extract_page_size(soup)
    current_page = _extract_current_page(page_url)
    total_pages = None
    if total_records is not None and page_size:
        total_pages = -(-total_records // page_size)  # ceil division, stdlib-only

    header_labels = _extract_header_labels(soup)

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        match = DETAIL_LINK_RE.search(anchor["href"])
        if not match:
            continue
        source_product_id = match.group(1)
        if source_product_id in seen_ids:
            continue  # defensive: a duplicate link to the same product on one page
        seen_ids.add(source_product_id)

        detail_url = urljoin(page_url, anchor["href"])
        product_name = anchor.get_text(strip=True)

        other_cell_texts = _sibling_cell_texts(anchor)
        sale_start_raw = other_cell_texts[0] if len(other_cell_texts) > 0 else ""
        sale_end_raw = other_cell_texts[1] if len(other_cell_texts) > 1 else ""

        if len(header_labels) >= 3:
            raw_fields = {
                header_labels[0]: product_name,
                header_labels[1]: sale_start_raw,
                header_labels[2]: sale_end_raw,
            }
        else:
            raw_fields = {"product_name": product_name, "column_1": sale_start_raw, "column_2": sale_end_raw}

        records.append(
            {
                "source": "tii",
                "source_product_id": source_product_id,
                "detail_url": detail_url,
                "source_product_url": detail_url,
                "company_name": "",
                "product_code": "",
                "product_name": product_name,
                "insurance_category": "",
                "insurance_type": "",
                "sale_start_date": _as_date_or_blank(sale_start_raw),
                "sale_end_date": _as_date_or_blank(sale_end_raw),
                "approval_date": "",
                "approval_number": "",
                "raw_fields": raw_fields,
                "documents": [],
            }
        )

    return {
        "total_records": total_records,
        "current_page": current_page,
        "total_pages": total_pages,
        "records": records,
    }


def _sibling_cell_texts(anchor) -> list[str]:
    """Non-empty text of every <td> in the anchor's row other than the one
    holding the anchor itself, in document order -- for this page's layout
    that's [sale_start_date, sale_end_date].
    """
    row = anchor.find_parent("tr")
    if row is None:
        return []
    texts: list[str] = []
    for cell in row.find_all("td"):
        if anchor in cell.find_all("a"):
            continue
        text = cell.get_text(strip=True)
        if text:
            texts.append(text)
    return texts
