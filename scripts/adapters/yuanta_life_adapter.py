"""
Collect Yuanta Life products from the official Nuxt API.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u5143\u5927\u4eba\u58fd"
BASE = "https://www.yuantalife.com.tw"
API_BASE = f"{BASE}/api/api"
DEFAULT_OUTPUT = BACKEND / "data" / "yuanta_life_adapter_report.json"


def get_company_id(conn) -> int | None:
    row = conn.execute(
        "SELECT id FROM insurance_companies WHERE short_name = ? OR name = ? LIMIT 1",
        (COMPANY_NAME, COMPANY_NAME),
    ).fetchone()
    return int(row["id"]) if row else None


def normalize_pdf_url(url: str | None) -> str:
    if not url:
        return ""
    return url.replace(":443", "")


def detail_url(big_coverage_uid: str, product_uid: str) -> str:
    return f"{BASE}/products/overview/{big_coverage_uid}/detail/?prodId={product_uid}"


def get_json(client: httpx.Client, path: str) -> Any:
    response = client.get(f"{API_BASE}{path}")
    response.raise_for_status()
    return response.json().get("result")


def collect(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        coverages = get_json(client, "/bigcoverage") or []
        for coverage in coverages:
            coverage_uid = coverage.get("uid") or ""
            if not coverage_uid:
                continue
            contracts_payload = get_json(client, f"/contract?bigCoverageId={coverage_uid}") or {}
            contracts = contracts_payload.get("contract") if isinstance(contracts_payload, dict) else contracts_payload
            for contract in contracts or []:
                product_uid = contract.get("uid") or ""
                if not product_uid or product_uid in seen:
                    continue
                seen.add(product_uid)
                detail_payload = get_json(client, f"/contract/{product_uid}/detail") or []
                detail = detail_payload[0] if detail_payload else contract
                big_coverage = detail.get("bigCoverage") or coverage
                category = big_coverage.get("title") or coverage.get("title") or "\u5176\u4ed6"
                code = (detail.get("code") or product_uid[:8]).strip()
                product_name = (detail.get("title") or contract.get("title") or code).strip()
                documents: list[dict[str, str]] = []
                for key, doc_type, title in [
                    ("clause", "terms", "\u689d\u6b3e\u6a23\u5f35"),
                    ("productDM", "dm", "\u5546\u54c1DM"),
                    ("instructions", "instructions", "\u6295\u4fdd\u898f\u5247"),
                ]:
                    pdf_url = normalize_pdf_url(detail.get(key))
                    if pdf_url:
                        documents.append({"document_type": doc_type, "title": title, "pdf_url": pdf_url})
                items.append(
                    {
                        "company": COMPANY_NAME,
                        "product_id": code,
                        "product_uid": product_uid,
                        "product_name": product_name,
                        "category": category,
                        "currency": (detail.get("currency") or {}).get("title") or "",
                        "source_url": detail_url(coverage_uid, product_uid),
                        "documents": documents,
                    }
                )
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
                    product_id, company_id, company_name, product_name, category, currency,
                    status, source, source_url, final_source_url, url_status, document_status, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', 'official_adapter', ?, ?, 'ok', ?, ?, datetime('now'))
                ON CONFLICT(product_id, company_name) DO UPDATE SET
                    company_id=excluded.company_id,
                    product_name=excluded.product_name,
                    category=excluded.category,
                    currency=excluded.currency,
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
                    item["currency"],
                    item["source_url"],
                    item["source_url"],
                    "ok" if item["documents"] else "missing",
                    json.dumps({"product_uid": item["product_uid"]}, ensure_ascii=False),
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
    parser = argparse.ArgumentParser(description="Collect Yuanta Life product and PDF inventory.")
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
