"""
Collect Hontai Life product documents from official product tables.

Hontai's product category pages render each product as a two-row table entry:
name/code/downloads first, then description. The download cell contains DM and
contract terms PDF links.
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
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from bs4 import BeautifulSoup
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u5b8f\u6cf0\u4eba\u58fd"
BASE = "https://www.hontai.com.tw"
DEFAULT_OUTPUT = BACKEND / "data" / "hontai_life_adapter_report.json"

CATEGORY_PATHS = {
    "18pages/products/17060615102094": "\u5718\u9ad4\u5546\u54c1",
    "18pages/products/17060614144241": "\u9280\u9aee\u65cf\u5546\u54c1",
    "18pages/products/17060615083706": "\u4fdd\u969c\u578b\u5546\u54c1",
    "18pages/products/17060615085378": "\u5fae\u578b\u4fdd\u96aa",
    "18pages/products/17060615090762": "\u65c5\u5e73\u96aa",
    "18pages/products/17060615093568": "OIU\u5546\u54c1",
    "18pages/products/21050410125796": "\u5c0f\u984d\u7d42\u8001\u4fdd\u96aa",
    "18pages/products/18100417143978": "\u5be6\u7269\u7d66\u4ed8",
    "18pages/products/21110915085278": "\u91d1\u878d\u53cb\u5584\u670d\u52d9\u5546\u54c1",
    "18pages/products/23050915145930": "\u5065\u4fdd\u5354\u540c\u5546\u4fdd",
    "18pages/products/23053014555085": "\u5546\u54c1\u5be9\u95b1\u671f",
    "18pages/products/24011617403346": "\u5ba2\u7fa4\u884c\u92b7\u5546\u54c1",
}


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


def product_id_from_row(code: str, product_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9-]+", "", code).upper()
    if normalized:
        return f"HONTAI-{normalized}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"HONTAI-{digest}"


def document_type_for(title: str) -> str:
    if "\u689d\u6b3e" in title:
        return "terms"
    if "DM" in title.upper():
        return "dm"
    return "supporting"


def collect_documents(row, source_url: str) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in row.select("a.download[href]"):
        title = clean_text(anchor.get_text(" ", strip=True))
        href = anchor.get("href") or ""
        if not title or ".pdf" not in href.lower():
            continue
        pdf_url = urljoin(source_url, href)
        if pdf_url in seen:
            continue
        seen.add(pdf_url)
        documents.append(
            {
                "document_type": document_type_for(title),
                "title": title,
                "pdf_url": pdf_url,
            }
        )
    return documents


def merge_item(items_by_id: dict[str, dict[str, Any]], item: dict[str, Any]) -> None:
    existing = items_by_id.get(item["product_id"])
    if not existing:
        items_by_id[item["product_id"]] = item
        return

    metadata = existing.setdefault("metadata", {})
    categories = set(metadata.get("categories", [existing["category"]]))
    categories.add(item["category"])
    metadata["categories"] = sorted(categories)

    source_pages = set(metadata.get("source_pages", [existing["source_url"]]))
    source_pages.add(item["source_url"])
    metadata["source_pages"] = sorted(source_pages)

    seen_urls = {doc["pdf_url"] for doc in existing["documents"]}
    for doc in item["documents"]:
        if doc["pdf_url"] not in seen_urls:
            existing["documents"].append(doc)
            seen_urls.add(doc["pdf_url"])


def collect(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items_by_id: dict[str, dict[str, Any]] = {}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True, verify=False) as client:
        for path, category in CATEGORY_PATHS.items():
            source_url = urljoin(BASE, path)
            response = client.get(source_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for row in soup.select("table.table tr"):
                name_cell = row.select_one("td.name")
                code_cell = row.select_one("td.code")
                if not name_cell or not code_cell:
                    continue
                product_name = clean_text(name_cell.get_text(" ", strip=True))
                code = clean_text(code_cell.get_text(" ", strip=True))
                documents = collect_documents(row, source_url)
                if not product_name or not code or not documents:
                    continue
                item = {
                    "company": COMPANY_NAME,
                    "product_id": product_id_from_row(code, product_name),
                    "product_name": product_name,
                    "category": category,
                    "source_url": source_url,
                    "documents": documents,
                    "metadata": {
                        "code": code,
                        "categories": [category],
                        "source_pages": [source_url],
                    },
                }
                merge_item(items_by_id, item)
                if limit > 0 and len(items_by_id) >= limit:
                    return list(items_by_id.values())[:limit]
    return list(items_by_id.values())


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
    parser = argparse.ArgumentParser(description="Collect Hontai Life product documents from official tables.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum products to collect. 0 means all.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    items = collect(args.limit)
    apply_counts = apply_items(items) if args.apply else {"products_upserted": 0, "documents_upserted": 0}
    payload = {
        "company": COMPANY_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": args.apply,
        "summary": {
            "products_seen": len(items),
            "documents_seen": sum(len(item["documents"]) for item in items),
            **apply_counts,
        },
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
