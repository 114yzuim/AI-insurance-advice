"""
Collect Nan Shan Life product terms from official PDF indexes.

Nan Shan publishes PDF index files where each product row has a clickable
contract-terms annotation. This adapter pairs extracted product-name rows with
the PDF annotation URIs in order.
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

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from pypdf import PdfReader
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u5357\u5c71\u4eba\u58fd"
BASE = "https://www.nanshanlife.com.tw/nanshanlife/portal-api/File"
DEFAULT_OUTPUT = BACKEND / "data" / "nanshan_life_adapter_report.json"

INDEXES = [
    {"file_id": "854", "category": "\u58fd\u96aa\u4fdd\u969c", "title": "\u500b\u4eba\u4eba\u58fd\u4fdd\u96aa\u5546\u54c1"},
    {"file_id": "915", "category": "\u5065\u5eb7\u91ab\u7642", "title": "\u500b\u4eba\u5065\u5eb7\u4fdd\u96aa\u5546\u54c1"},
    {"file_id": "919", "category": "\u610f\u5916\u50b7\u5bb3", "title": "\u500b\u4eba\u50b7\u5bb3\u4fdd\u96aa\u5546\u54c1"},
    {"file_id": "923", "category": "\u5065\u5eb7\u91ab\u7642", "title": "\u500b\u4eba\u50b7\u5bb3\u96aa\u66a8\u5065\u5eb7\u96aa\u5546\u54c1"},
    {"file_id": "924", "category": "\u5e74\u91d1\u4fdd\u96aa", "title": "\u500b\u4eba\u5e74\u91d1\u4fdd\u96aa\u5546\u54c1"},
]


def get_company_id(conn) -> int | None:
    row = conn.execute(
        "SELECT id FROM insurance_companies WHERE short_name = ? OR name = ? LIMIT 1",
        (COMPANY_NAME, COMPANY_NAME),
    ).fetchone()
    return int(row["id"]) if row else None


def index_url(file_id: str) -> str:
    return f"{BASE}/{file_id}"


def download_index(client: httpx.Client, file_id: str) -> bytes:
    response = client.get(index_url(file_id))
    response.raise_for_status()
    return response.content


def extract_links(reader: PdfReader) -> list[str]:
    links: list[str] = []
    for page in reader.pages:
        for annot_ref in page.get("/Annots") or []:
            annot = annot_ref.get_object()
            action = annot.get("/A") or {}
            uri = action.get("/URI") if action else None
            if uri and "/Products/rule/" in uri and uri not in links:
                links.append(str(uri))
    return links


def clean_product_name(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = line.replace(" 請按此下載", "").replace("請按此下載", "").strip()
    return line


def extract_product_names(reader: PdfReader) -> list[str]:
    names: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = clean_product_name(raw_line)
            if not line or "\u8acb\u6309\u6b64\u4e0b\u8f09" in raw_line and not line:
                continue
            if "\u8acb\u6309\u6b64\u4e0b\u8f09" not in raw_line:
                continue
            if not line.startswith(COMPANY_NAME):
                continue
            names.append(line)
    return names


def product_id_from_url(url: str, product_name: str) -> str:
    stem = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".pdf")
    if stem:
        return stem.upper()
    return hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:10].upper()


def collect(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    tmp_dir = BACKEND / "data" / "adapter_cache"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True, verify=False) as client:
        for index in INDEXES:
            file_id = index["file_id"]
            content = download_index(client, file_id)
            cache_path = tmp_dir / f"nanshan_index_{file_id}.pdf"
            cache_path.write_bytes(content)
            reader = PdfReader(str(cache_path))
            names = extract_product_names(reader)
            links = extract_links(reader)
            for product_name, pdf_url in zip(names, links):
                key = (product_name, pdf_url)
                if key in seen:
                    continue
                seen.add(key)
                item = {
                    "company": COMPANY_NAME,
                    "product_id": product_id_from_url(pdf_url, product_name),
                    "product_name": product_name,
                    "category": index["category"],
                    "source_url": index_url(file_id),
                    "source_index_title": index["title"],
                    "documents": [
                        {
                            "document_type": "terms",
                            "title": "\u5951\u7d04\u689d\u6b3e",
                            "pdf_url": pdf_url,
                        }
                    ],
                }
                items.append(item)
                if limit > 0 and len(items) >= limit:
                    return items
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
                    json.dumps({"source_index_title": item["source_index_title"]}, ensure_ascii=False),
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
    parser = argparse.ArgumentParser(description="Collect Nan Shan Life terms inventory from official PDF indexes.")
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
