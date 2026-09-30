"""Parse an IB (保險業公開資訊觀測站) company product-list page (Property_Layout.aspx)
into SourceProductRecords.

Verified live (2026-09-13) against
https://ins-info.ib.gov.tw/customer/Property_Layout.aspx?UID=03557115:

  - A bare GET (no search submitted) shows the search form with an empty
    results area -- see `fixtures/real_property_layout_03557115.html`.
  - POSTing that same page's own search form with blank product_code/keyword
    (see query_client.py) returns a real, populated product list: an ASP.NET
    DataGrid, `<table id="ctl00_MainContent_DataGridSearchResults">`, one
    `<tr>` per product with two `<span>`s (product code, product name) and a
    `<select id="func" onchange="goDetail(this, '<productCode>')">` offering
    5 document-type choices (1=基本資訊/basic info, 2=條款內容/policy terms,
    3=短期費率表/short-term rate table, 4=費用率與退費係數表/commission+refund
    table, 5=理賠申請文件及程序/claim documents+procedure). Pagination is a
    plain `?Page=N&UID=...` query string, not a postback -- see
    query_client.py's docstring for the caveat on when that's been confirmed
    to work.

Function 1 (基本資訊) is treated as each product's canonical `detail_url`;
`raw_fields["function_options"]` carries the label for every function
number so scripts/resolve_ib_product_details.py knows what to call each of
the 5 detail fetches without re-deriving it. Nothing here submits any
*other* form or drives a postback beyond the one query() the CLI already
performs -- see scripts/sources/ib_disclosure/README.md for the full scope.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from document_parser import extract_documents  # noqa: E402
from source import SourceProductRecord  # noqa: E402

UID_RE = re.compile(r"[?&]UID=([^&#]+)", re.I)
PAGE_INFO_RE = re.compile(r"目前在第\s*(\d+)\s*頁[,，]\s*共\s*(\d+)\s*頁")

# Verified live (2026-09-13): the function <select>'s own <option> labels,
# in order. IB's goDetail() JS maps a selected value N straight to
# property5-1-{N}.aspx.
FUNCTION_OPTIONS: dict[str, str] = {
    "1": "基本資訊",
    "2": "條款內容",
    "3": "短期費率表",
    "4": "銷售予金融消費者之保險商品預定附加費用率與保費退費係數表",
    "5": "理賠申請文件及程序",
}


def _extract_company_name(soup: BeautifulSoup) -> str:
    """From the page's own <h2 class="tb4">公司名稱 - 資訊公開說明文件</h2>.

    Chosen over the breadcrumb link (also present, also carries the company
    name) because it's a single, unambiguous element rather than "the
    second of N breadcrumb links", which is more fragile if IB ever adds or
    reorders breadcrumb segments.
    """
    heading = soup.find("h2", class_="tb4")
    if heading is None:
        return ""
    text = heading.get_text(strip=True)
    return text.split("-", 1)[0].strip() if "-" in text else text.strip()


def _extract_uid(page_url: str, soup: BeautifulSoup) -> str:
    match = UID_RE.search(page_url)
    if match:
        return match.group(1)
    form = soup.find("form")
    if form and form.get("action"):
        match = UID_RE.search(form["action"])
        if match:
            return match.group(1)
    return ""


def _extract_pagination(soup: BeautifulSoup) -> dict[str, Any]:
    """current_page / total_pages / has_next_page from the "目前在第 N 頁，
    共 M 頁" footer text -- more reliable than counting pager links, which
    can be hidden/absent at either boundary.
    """
    match = PAGE_INFO_RE.search(soup.get_text())
    if not match:
        return {"current_page": 1, "total_pages": 1, "has_next_page": False}
    current_page, total_pages = int(match.group(1)), int(match.group(2))
    return {
        "current_page": current_page,
        "total_pages": total_pages,
        "has_next_page": current_page < total_pages,
    }


def _find_data_grid(soup: BeautifulSoup):
    """The populated results grid, keyed on its own stable ASP.NET control id.

    Precise on purpose -- IB's generic `class="table"` appears on several
    unrelated tables on this page, so a text/class-based search risks
    matching the wrong one. This id is specific to the search-results
    DataGrid control and was confirmed live.
    """
    return soup.find("table", id="ctl00_MainContent_DataGridSearchResults")


def _extract_product_rows(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Each product row from the real DataGrid, if a search was submitted
    and returned results. Returns [] for the bare (no-search) search-entry
    page -- see module docstring.
    """
    grid = _find_data_grid(soup)
    if grid is None:
        return []

    products = []
    for row in grid.find_all("tr"):
        spans = row.find_all("span")
        code_span = next((s for s in spans if (s.get("id") or "").lower().endswith("lbproductcode")), None)
        if code_span is None:
            continue  # not a product row (e.g. a header row, if the grid ever renders one)
        product_code = code_span.get_text(strip=True)
        name_spans = [s for s in spans if s is not code_span]
        product_name = name_spans[0].get_text(strip=True) if name_spans else ""
        products.append({"product_code": product_code, "product_name": product_name, "row_html": str(row)})
    return products


def parse_property_page(
    html: str,
    page_url: str,
    source_html_path: str | None = None,
    insurance_category: str | None = None,
) -> list[SourceProductRecord]:
    """Parse one IB company product-list page (a bare search entry, or a
    POST'd search-results page) into a list of SourceProductRecords.

    `insurance_category` is passed through from the caller's company seed
    entry (IB itself doesn't print this) -- see
    backend/data/ib_companies_seed.json.
    """
    soup = BeautifulSoup(html, "html.parser")
    company_name = _extract_company_name(soup)
    uid = _extract_uid(page_url, soup)
    fetched_at = datetime.now(timezone.utc).isoformat()
    pagination = _extract_pagination(soup)

    product_rows = _extract_product_rows(soup)

    if not product_rows:
        return [
            SourceProductRecord(
                source_product_id=uid or page_url,
                detail_url=page_url,
                source_product_url=page_url,
                fetched_at=fetched_at,
                company_name=company_name or None,
                company_uid=uid or None,
                insurance_category=insurance_category,
                documents=extract_documents(html, base_url=page_url),
                raw_fields={
                    "company_name": company_name,
                    "uid": uid,
                    "page_kind": "company_search_entry_no_results",
                    "note": (
                        "No product rows were found on this page. Either this is a bare "
                        "search-entry URL with no query submitted, or a submitted query "
                        "genuinely matched nothing -- see property_parser.py's module docstring."
                    ),
                    **pagination,
                },
                source_html_path=source_html_path,
            )
        ]

    base_uid = uid
    records = []
    for row in product_rows:
        product_code = row["product_code"]
        detail_url = f"https://ins-info.ib.gov.tw/customer/property5-1-1.aspx?UID={base_uid}&proc={product_code}"
        source_product_id = f"{base_uid}:{product_code}" if product_code else f"{base_uid}:{row['product_name']}"
        records.append(
            SourceProductRecord(
                source_product_id=source_product_id,
                detail_url=detail_url,
                source_product_url=page_url,
                fetched_at=fetched_at,
                company_name=company_name or None,
                company_uid=base_uid or None,
                insurance_category=insurance_category,
                product_code=product_code or None,
                product_name=row["product_name"] or None,
                raw_fields={
                    "function_options": dict(FUNCTION_OPTIONS),
                    **pagination,
                },
                source_html_path=source_html_path,
            )
        )
    return records
