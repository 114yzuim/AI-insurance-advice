"""
Collect Mercuries Life product documents from official insurance pages.

The MLI product pages render product cards in HTML. Each card contains a
product name and PDF download endpoints served through /sites/Satellite.
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
from bs4 import BeautifulSoup
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u4e09\u5546\u7f8e\u90a6\u4eba\u58fd"
BASE = "https://www.mli.com.tw"
DEFAULT_OUTPUT = BACKEND / "data" / "mli_life_adapter_report.json"

CATEGORY_PATHS = {
    "sites/mliportal/insurance/popularity": "\u4eba\u6c23\u5546\u54c1",
    "sites/mliportal/insurance/protection-regular": "\u5b9a\u671f\u58fd\u96aa",
    "sites/mliportal/insurance/protection-lifetime": "\u7d42\u8eab\u58fd\u96aa",
    "sites/mliportal/insurance/reimbursement-lifetime": "\u9084\u672c\u578b\u7d42\u8eab\u4fdd\u96aa",
    "sites/mliportal/insurance/reimbursement-pension": "\u9084\u672c\u578b\u990a\u8001\u4fdd\u96aa",
    "sites/mliportal/insurance/spot-annuity": "\u5373\u671f\u5e74\u91d1",
    "sites/mliportal/insurance/deferred-annuity": "\u905e\u5ef6\u5e74\u91d1",
    "sites/mliportal/insurance/health-hospitalization": "\u4f4f\u9662\u91ab\u7642\u96aa",
    "sites/mliportal/insurance/health-cancer": "\u764c\u75c7\u91cd\u75be\u96aa",
    "sites/mliportal/insurance/health-broken": "\u9577\u7167\u5931\u80fd\u96aa",
    "sites/mliportal/insurance/health-exemption": "\u8c41\u514d\u4fdd\u96aa\u8cbb",
    "sites/mliportal/insurance/accidental": "\u610f\u5916\u50b7\u5bb3\u96aa",
    "sites/mliportal/insurance/travel": "\u65c5\u884c\u5e73\u5b89\u96aa",
    "sites/mliportal/insurance/bank-regular": "\u9280\u884c\u901a\u8def\u5b9a\u671f\u58fd\u96aa",
    "sites/mliportal/insurance/bank-lifetime": "\u9280\u884c\u901a\u8def\u7d42\u8eab\u58fd\u96aa",
    "sites/mliportal/insurance/bank-pension": "\u9280\u884c\u901a\u8def\u990a\u8001\u4fdd\u96aa",
    "sites/mliportal/insurance/endorsements": "\u6279\u8a3b\u689d\u6b3e",
    "sites/mliportal/insurance/group": "\u5718\u96aa\u5c08\u5340",
    "sites/mliportal/insurance/group-regular": "\u5718\u9ad4\u5b9a\u671f\u58fd\u96aa",
    "sites/mliportal/insurance/group-health": "\u5718\u9ad4\u5065\u5eb7\u91ab\u7642\u96aa",
    "sites/mliportal/insurance/group-accidental": "\u5718\u9ad4\u610f\u5916\u50b7\u5bb3\u96aa",
    "sites/mliportal/insurance/protection-area": "\u4fdd\u969c\u578b\u5546\u54c1\u5c08\u5340",
    "sites/mliportal/insurance/spillover-policy": "\u5916\u6ea2\u4fdd\u55ae\u5c08\u5340",
    "sites/mliportal/insurance/oiu": "OIU\u5546\u54c1",
    "sites/mliportal/insurance/aging": "\u9ad8\u9f61\u5316\u5546\u54c1",
    "sites/mliportal/insurance/smallwholelife": "\u5c0f\u984d\u7d42\u8001\u4fdd\u96aa",
    "sites/mliportal/insurance/micro": "\u5fae\u578b\u4fdd\u96aa",
    "sites/mliportal/insurance/working-overseas": "\u6d77\u5916\u5ea6\u5047\u9752\u5e74\u6253\u5de5",
}

SKIP_TITLES = ("\u53cb\u5584\u95b1\u8b80",)


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


def product_id_from_name(product_name: str) -> str:
    matches = re.findall(r"\(([A-Z0-9-]{2,})\)", product_name)
    if matches:
        return f"MLI-{matches[-1].upper()}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"MLI-{digest}"


def document_type_for(title: str) -> str:
    if "\u689d\u6b3e" in title:
        return "terms"
    if "DM" in title.upper():
        return "dm"
    return "supporting"


def blob_id(url: str) -> str:
    parsed = urlparse(url)
    return parse_qs(parsed.query).get("blobwhere", [""])[0]


def collect_documents(card, source_url: str) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in card.select(".right-section a[href]"):
        title = clean_text(anchor.get_text(" ", strip=True))
        if not title or any(part in title for part in SKIP_TITLES):
            continue
        if "\u4e86\u89e3\u66f4\u591a" in title:
            continue
        if "\u689d\u6b3e" not in title and "DM" not in title.upper():
            continue
        pdf_url = urljoin(source_url, anchor.get("href") or "")
        if not blob_id(pdf_url) or pdf_url in seen:
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


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items_by_id: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    with httpx.Client(headers=headers, timeout=45, follow_redirects=True, verify=False) as client:
        for path, category in CATEGORY_PATHS.items():
            source_url = urljoin(BASE, path)
            try:
                response = client.get(source_url)
                response.raise_for_status()
            except Exception as exc:
                errors.append({"source_url": source_url, "error": str(exc)[:240]})
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for card in soup.select(".products-item"):
                heading = card.select_one("h2.products-name")
                product_name = clean_text(heading.get_text(" ", strip=True) if heading else "")
                documents = collect_documents(card, source_url)
                if not product_name or not documents:
                    continue
                item = {
                    "company": COMPANY_NAME,
                    "product_id": product_id_from_name(product_name),
                    "product_name": product_name,
                    "category": category,
                    "source_url": source_url,
                    "documents": documents,
                    "metadata": {
                        "categories": [category],
                        "source_pages": [source_url],
                    },
                }
                merge_item(items_by_id, item)
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
    parser = argparse.ArgumentParser(description="Collect Mercuries Life product documents from official pages.")
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
