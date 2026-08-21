"""
Collect AIA Taiwan product clauses from the official clauses page.

The AIA page exposes individual and group product clauses as ordinary HTML
tables/download lists, with PDF files under /content/dam/tw-wise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from bs4 import BeautifulSoup
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u53cb\u90a6\u4eba\u58fd"
BASE = "https://www.aia.com.tw"
SOURCE_URL = f"{BASE}/zh-tw/help-and-support/important-info/clauses"
DEFAULT_OUTPUT = BACKEND / "data" / "aia_life_adapter_report.json"


def get_company_id(conn) -> int | None:
    row = conn.execute(
        """
        SELECT id
        FROM insurance_companies
        WHERE short_name = ?
           OR name = ?
           OR name LIKE ?
        LIMIT 1
        """,
        (COMPANY_NAME, COMPANY_NAME, f"%{COMPANY_NAME}%"),
    ).fetchone()
    return int(row["id"]) if row else None


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def filename_for(url: str) -> str:
    return unquote(urlparse(url).path.rsplit("/", 1)[-1])


def product_id_from_url(pdf_url: str, product_name: str) -> str:
    filename = filename_for(pdf_url)
    match = re.search(r"\(([A-Z0-9-]{2,})\)", filename)
    if match:
        return f"AIA-{match.group(1).upper()}"
    stem = re.sub(r"[^A-Za-z0-9]+", "", filename.split(".", 1)[0]).upper()
    if stem:
        return f"AIA-{stem[:32]}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"AIA-{digest}"


def category_for(product_name: str) -> str:
    if "\u5718\u9ad4" in product_name:
        return "\u5718\u9ad4\u4fdd\u96aa"
    if "\u610f\u5916" in product_name or "\u50b7\u5bb3" in product_name:
        return "\u610f\u5916\u50b7\u5bb3"
    if (
        "\u91ab\u7642" in product_name
        or "\u5065\u5eb7" in product_name
        or "\u764c" in product_name
        or "\u75c5" in product_name
        or "\u624b\u8853" in product_name
        or "\u4f4f\u9662" in product_name
    ):
        return "\u5065\u5eb7\u91ab\u7642"
    if "\u5e74\u91d1" in product_name:
        return "\u5e74\u91d1\u4fdd\u96aa"
    if "\u6295\u8cc7" in product_name:
        return "\u6295\u8cc7\u578b\u4fdd\u96aa"
    return "\u58fd\u96aa\u4fdd\u969c"


def document_title(product_name: str, pdf_url: str) -> str:
    filename = filename_for(pdf_url)
    if filename:
        return f"{product_name} {filename}"
    return f"{product_name} \u5951\u7d04\u689d\u6b3e"


def add_item(
    items_by_id: dict[str, dict[str, Any]],
    product_name: str,
    pdf_url: str,
    source_section: str,
) -> None:
    product_name = clean_text(product_name)
    if COMPANY_NAME not in product_name or ".pdf" not in pdf_url.lower():
        return

    full_pdf_url = urljoin(BASE, pdf_url)
    product_id = product_id_from_url(full_pdf_url, product_name)
    item = items_by_id.get(product_id)
    if not item:
        item = {
            "company": COMPANY_NAME,
            "product_id": product_id,
            "product_name": product_name,
            "category": category_for(product_name),
            "source_url": SOURCE_URL,
            "documents": [],
            "metadata": {
                "source_sections": [source_section],
                "source": "official_clauses_page",
            },
        }
        items_by_id[product_id] = item
    elif source_section not in item["metadata"]["source_sections"]:
        item["metadata"]["source_sections"].append(source_section)

    if full_pdf_url not in {doc["pdf_url"] for doc in item["documents"]}:
        item["documents"].append(
            {
                "document_type": "terms",
                "title": document_title(product_name, full_pdf_url),
                "pdf_url": full_pdf_url,
            }
        )


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items_by_id: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    try:
        response = httpx.get(SOURCE_URL, headers=headers, timeout=45, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return [], [{"source_url": SOURCE_URL, "error": str(exc)[:240]}]

    soup = BeautifulSoup(response.text, "html.parser")
    for tr in soup.select("table.table_aia tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        product_name = clean_text(cells[0].get_text(" ", strip=True))
        anchor = tr.find("a", href=True)
        if anchor:
            add_item(items_by_id, product_name, anchor["href"], "individual_terms_table")
            if limit > 0 and len(items_by_id) >= limit:
                return list(items_by_id.values())[:limit], errors

    for anchor in soup.select("a.cmp-download__action[href]"):
        product_name = clean_text(anchor.get_text(" ", strip=True))
        add_item(items_by_id, product_name, anchor["href"], "group_terms_downloads")
        if limit > 0 and len(items_by_id) >= limit:
            return list(items_by_id.values())[:limit], errors

    return list(items_by_id.values()), errors


def apply_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"products_upserted": 0, "documents_upserted": 0}
    with get_inventory_connection() as conn:
        company_id = get_company_id(conn)
        for item in items:
            conn.execute(
                """
                INSERT INTO insurance_products (
                    product_id, company_id, company_name, product_name, category,
                    status, source, source_url, final_source_url, url_status, document_status, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'active', 'official_adapter', ?, ?, 'ok', 'ok', ?, datetime('now'))
                ON CONFLICT(product_id, company_name) DO UPDATE SET
                    company_id=excluded.company_id,
                    product_name=excluded.product_name,
                    category=excluded.category,
                    status=excluded.status,
                    source=excluded.source,
                    source_url=excluded.source_url,
                    final_source_url=excluded.final_source_url,
                    url_status=excluded.url_status,
                    document_status=excluded.document_status,
                    metadata=excluded.metadata,
                    updated_at=datetime('now')
                """,
                (
                    item["product_id"],
                    company_id,
                    COMPANY_NAME,
                    item["product_name"],
                    item["category"],
                    item["source_url"],
                    item["source_url"],
                    json.dumps(item["metadata"], ensure_ascii=False),
                ),
            )
            counts["products_upserted"] += 1
            product_db_id = conn.execute(
                "SELECT id FROM insurance_products WHERE product_id = ? AND company_name = ?",
                (item["product_id"], COMPANY_NAME),
            ).fetchone()["id"]
            for doc in item["documents"]:
                conn.execute(
                    """
                    INSERT INTO policy_documents (
                        product_db_id, document_type, title, pdf_url, final_pdf_url,
                        pdf_status, text_status, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'ok', 'pending', datetime('now'))
                    ON CONFLICT(product_db_id, pdf_url) DO UPDATE SET
                        document_type=excluded.document_type,
                        title=excluded.title,
                        final_pdf_url=excluded.final_pdf_url,
                        pdf_status=excluded.pdf_status,
                        updated_at=datetime('now')
                    """,
                    (product_db_id, doc["document_type"], doc["title"], doc["pdf_url"], doc["pdf_url"]),
                )
                counts["documents_upserted"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect AIA Taiwan product clauses from official page.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum products to collect. 0 means all.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    items, errors = collect(args.limit)
    apply_counts = apply_items(items) if args.apply else {"products_upserted": 0, "documents_upserted": 0}
    payload = {
        "company": COMPANY_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": args.apply,
        "summary": {
            "products_seen": len(items),
            "documents_seen": sum(len(item["documents"]) for item in items),
            "errors": len(errors),
            **apply_counts,
        },
        "errors": errors,
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
