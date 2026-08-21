"""
Collect PCA Life Taiwan product PDFs from the official e-consultant page.

The page lists products with a pair of official PDF links: product brief and
sample policy terms. This gives the inventory an official, verifiable PCA
starting set without guessing from generic site search results.
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

COMPANY_NAME = "\u4fdd\u8aa0\u4eba\u58fd"
BASE = "https://www.pcalife.com.tw"
SOURCE_URL = f"{BASE}/zh/products/mm/explore-all/"
DEFAULT_OUTPUT = BACKEND / "data" / "prudential_life_adapter_report.json"


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


def product_key_from_url(url: str, product_name: str) -> str:
    stem = filename_for(url).split(".", 1)[0]
    stem = re.sub(r"(?i)([_-]?dm|[_-]?brochure)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    if stem:
        return f"PCA-{stem[:42]}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"PCA-{digest}"


def product_name_from_title(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r"\u5546\u54c1\u7c21\u4ecb$", "", title)
    title = re.sub(r"\u689d\u6b3e\u6a23\u5f35$", "", title)
    return clean_text(title)


def document_type_for(title: str) -> str:
    if "\u689d\u6b3e" in title:
        return "terms"
    if "\u5546\u54c1\u7c21\u4ecb" in title or "DM" in title.upper():
        return "dm"
    return "supporting"


def category_for(product_name: str) -> str:
    if "\u91ab\u7642" in product_name or "\u5065\u5eb7" in product_name or "\u764c" in product_name:
        return "\u5065\u5eb7\u91ab\u7642"
    if "\u610f\u5916" in product_name or "\u50b7\u5bb3" in product_name:
        return "\u610f\u5916\u50b7\u5bb3"
    if "\u5e74\u91d1" in product_name:
        return "\u5e74\u91d1\u4fdd\u96aa"
    if "\u6295\u8cc7" in product_name or "\u8b8a\u984d" in product_name:
        return "\u6295\u8cc7\u578b\u4fdd\u96aa"
    return "\u58fd\u96aa\u4fdd\u969c"


def merge_document(items_by_id: dict[str, dict[str, Any]], title: str, pdf_url: str) -> None:
    product_name = product_name_from_title(title)
    if not product_name.startswith(COMPANY_NAME):
        return
    product_id = product_key_from_url(pdf_url, product_name)
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
                "source": "official_mm_product_page",
                "filenames": [],
            },
        }
        items_by_id[product_id] = item
    if pdf_url not in {doc["pdf_url"] for doc in item["documents"]}:
        item["documents"].append(
            {
                "document_type": document_type_for(title),
                "title": title,
                "pdf_url": pdf_url,
            }
        )
        item["metadata"]["filenames"].append(filename_for(pdf_url))


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    try:
        response = httpx.get(SOURCE_URL, headers=headers, timeout=45, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return [], [{"source_url": SOURCE_URL, "error": str(exc)[:240]}]

    soup = BeautifulSoup(response.text, "html.parser")
    items_by_id: dict[str, dict[str, Any]] = {}
    for anchor in soup.find_all("a", href=True):
        title = clean_text(anchor.get_text(" ", strip=True))
        pdf_url = urljoin(SOURCE_URL, anchor["href"])
        if ".pdf" not in pdf_url.lower() or not title.startswith(COMPANY_NAME):
            continue
        if "\u5546\u54c1\u7c21\u4ecb" not in title and "\u689d\u6b3e\u6a23\u5f35" not in title:
            continue
        merge_document(items_by_id, title, pdf_url)
        if limit > 0 and len(items_by_id) >= limit:
            break
    return list(items_by_id.values())[:limit] if limit > 0 else list(items_by_id.values()), []


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
    parser = argparse.ArgumentParser(description="Collect PCA Life official e-consultant product PDFs.")
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
