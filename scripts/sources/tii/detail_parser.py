"""Parse a TII product detail page into a SourceProductRecord.

CAUTION -- not yet verified against a live sample.
----------------------------------------------------
We have not been able to capture a real TII detail page (that requires
solving the site's CAPTCHA, which this project doesn't automate -- see
client.py). This parser is written defensively against the label:value
table layout ASP.NET WebForms sites like this one almost always use
(`<tr><td>label</td><td>value</td></tr>`), plus a keyword map from the field
labels visible on TII's own query form (公司名稱/保險類別/銷售日/停售日/核准
日期/核准文號/送審方式). Treat `raw_fields` as the source of truth until this
has been run against a real saved page and the keyword map corrected to
match; nothing is silently dropped even if a label isn't recognized.

Update KNOWN_FIELD_KEYWORDS (and add a regression fixture under
scripts/sources/tii/fixtures/) the first time a real detail page is on hand.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from document_parser import extract_documents  # noqa: E402
from source import SourceProductRecord  # noqa: E402

# (keyword, field name) -- first match wins, checked in order so more
# specific labels (e.g. "核准文號") are listed before generic ones.
KNOWN_FIELD_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("公司名稱", "company_name"),
    ("公司名�", "company_name"),  # tolerate mojibake from a mis-decoded charset
    ("商品名稱", "product_name"),
    ("保險類別", "insurance_type"),
    ("公司類別", "insurance_category"),
    ("銷售日", "sale_start_date"),
    ("停售日", "sale_end_date"),
    ("核准日期", "approval_date"),
    ("核備日期", "approval_date"),
    ("核准文號", "approval_number"),
    ("核備文號", "approval_number"),
    ("送審方式", "review_method"),
    ("審查方式", "review_method"),
)


def _extract_label_value_pairs(soup: BeautifulSoup) -> dict[str, str]:
    """Collect every 2-cell table row as {first_cell_text: second_cell_text}.

    Later rows win on a duplicate label (last-one-wins), which matches how
    ASP.NET GridViews typically repeat a header-like label column.
    """
    pairs: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True)
        value = cells[1].get_text(strip=True)
        if label and value:
            pairs[label] = value
    return pairs


def _map_known_fields(raw_fields: dict[str, str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for label, value in raw_fields.items():
        for keyword, field_name in KNOWN_FIELD_KEYWORDS:
            if keyword in label and field_name not in mapped:
                mapped[field_name] = value
                break
    return mapped


def parse_detail_page(
    html: str,
    *,
    detail_url: str,
    source_product_id: str,
    source_html_path: str | None = None,
) -> SourceProductRecord:
    soup = BeautifulSoup(html, "html.parser")
    raw_fields = _extract_label_value_pairs(soup)
    mapped = _map_known_fields(raw_fields)
    documents = extract_documents(html, base_url=detail_url)

    return SourceProductRecord(
        source_product_id=source_product_id,
        detail_url=detail_url,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        company_name=mapped.get("company_name"),
        product_name=mapped.get("product_name"),
        insurance_category=mapped.get("insurance_category"),
        insurance_type=mapped.get("insurance_type"),
        sale_start_date=mapped.get("sale_start_date"),
        sale_end_date=mapped.get("sale_end_date"),
        approval_date=mapped.get("approval_date"),
        approval_number=mapped.get("approval_number"),
        filing_number=mapped.get("filing_number"),
        review_method=mapped.get("review_method"),
        documents=documents,
        raw_fields=raw_fields,
        source_html_path=source_html_path,
    )
