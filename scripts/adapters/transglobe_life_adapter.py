"""
Collect TransGlobe Life product terms from the official Media API.
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
from urllib.parse import parse_qs, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u5168\u7403\u4eba\u58fd"
BASE = "https://www.transglobe.com.tw"
DEFAULT_OUTPUT = BACKEND / "data" / "transglobe_life_adapter_report.json"
API_ID_CLAUSE_REVIEW = "8dbb8fcec20f4f60a335c7e6a36af388"
SESSION_KEY = "d64c8a19669945759fbfdf336263929a"


def get_company_id(conn) -> int | None:
    row = conn.execute(
        "SELECT id FROM insurance_companies WHERE short_name = ? OR name = ? LIMIT 1",
        (COMPANY_NAME, COMPANY_NAME),
    ).fetchone()
    return int(row["id"]) if row else None


def clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\s*\([^)]*銷售日期[^)]*\)\s*$", "", name)
    name = name.replace("契約條款", "").strip()
    return name


def product_id_from_item(name: str, url: str) -> str:
    file_name = parse_qs(urlparse(url).query).get("file", [""])[0]
    if file_name:
        code = file_name.split("_", 1)[0].removesuffix(".pdf")
        if code:
            return code.upper()
    match = re.search(r"\(([A-Z0-9]{2,})\)", name)
    if match:
        return match.group(1).upper()
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:10].upper()


def category_for(name: str) -> str:
    if "\u50b7\u5bb3" in name or "\u610f\u5916" in name:
        return "\u610f\u5916\u50b7\u5bb3"
    if "\u91ab\u7642" in name or "\u5065\u5eb7" in name or "\u764c" in name or "\u75c5" in name:
        return "\u5065\u5eb7\u91ab\u7642"
    if "\u5e74\u91d1" in name:
        return "\u5e74\u91d1\u4fdd\u96aa"
    if "\u6295\u8cc7" in name:
        return "\u6295\u8cc7\u578b\u4fdd\u96aa"
    return "\u58fd\u96aa\u4fdd\u969c"


def collect(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    payload = {"API_ID": API_ID_CLAUSE_REVIEW, "session_key": SESSION_KEY, "pageNo": 1}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True, verify=False) as client:
        response = client.post(f"{BASE}/api/mediaAPI?v=1", json=payload)
        response.raise_for_status()
        data = response.json()
    items: list[dict[str, Any]] = []
    for row in data.get("datas", []):
        raw_name = row.get("name") or ""
        url = row.get("url") or ""
        if not raw_name or not url:
            continue
        product_name = clean_name(raw_name)
        pdf_url = urljoin(BASE, url)
        product_id = product_id_from_item(raw_name, url)
        items.append(
            {
                "company": COMPANY_NAME,
                "product_id": product_id,
                "product_name": product_name,
                "category": category_for(product_name),
                "source_url": f"{BASE}/product-clause.html",
                "documents": [
                    {
                        "document_type": "terms",
                        "title": "\u5951\u7d04\u689d\u6b3e",
                        "pdf_url": pdf_url,
                    }
                ],
            }
        )
        if limit > 0 and len(items) >= limit:
            break
    return items


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
                    json.dumps({"source": "mediaAPI.clause_review"}, ensure_ascii=False),
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
    parser = argparse.ArgumentParser(description="Collect TransGlobe Life terms inventory from official Media API.")
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
