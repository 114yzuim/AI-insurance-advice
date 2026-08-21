"""
Repair Taiwan Life inventory URLs from the legacy portal API crawl.

Taiwan Life currently returns a browser/WAF "Request Rejected" page to the
plain HTTP downloader for many portal-api PDF links. This adapter does the
safe repair work we can do without a browser session:

1. Convert old product detail API URLs to public product pages.
2. Keep original portal-api/File URLs as candidate PDF URLs.
3. Mark affected documents as browser-required instead of non-PDF.
4. Emit a report for the later browser/TLS downloader step.
"""

from __future__ import annotations

import argparse
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

from inventory_db import get_inventory_connection, row_to_dict

COMPANY_NAME = "\u53f0\u7063\u4eba\u58fd"
DEFAULT_OUTPUT = BACKEND / "data" / "taiwan_life_adapter_report.json"

PRODUCT_DETAIL_RE = re.compile(r"/portal-api/ProductDetail/([^/?#]+).*?[?&]type_id=(\d+)", re.I)
PUBLIC_PRODUCT_RE = re.compile(r"/product/(\d+)/([^/?#]+)", re.I)
FILE_RE = re.compile(r"/portal-api/File/([^/?#]+)", re.I)


def public_product_url(source_url: str, product_id: str) -> str:
    source_url = source_url or ""
    public_match = PUBLIC_PRODUCT_RE.search(source_url)
    if public_match:
        type_id, public_product_id = public_match.groups()
        return f"https://www.taiwanlife.com/product/{type_id}/{public_product_id}"

    detail_match = PRODUCT_DETAIL_RE.search(source_url)
    if detail_match:
        detail_product_id, type_id = detail_match.groups()
        return f"https://www.taiwanlife.com/product/{type_id}/{detail_product_id}"

    return source_url if source_url.startswith("https://www.taiwanlife.com/product/") else ""


def extract_file_id(pdf_url: str) -> str:
    match = FILE_RE.search(pdf_url or "")
    return match.group(1) if match else ""


def collect_candidates(limit: int) -> list[dict[str, Any]]:
    limit_clause = "" if limit <= 0 else "LIMIT ?"
    params: list[Any] = [COMPANY_NAME]
    if limit > 0:
        params.append(limit)

    with get_inventory_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                p.id AS product_db_id,
                p.product_id,
                p.product_name,
                p.category,
                p.source_url,
                p.final_source_url,
                p.url_status,
                p.document_status,
                d.id AS document_id,
                d.document_type,
                d.title AS document_title,
                d.pdf_url,
                d.final_pdf_url,
                d.pdf_status,
                d.text_status
            FROM insurance_products p
            LEFT JOIN policy_documents d ON d.product_db_id = p.id
            WHERE p.company_name = ?
            ORDER BY p.product_id, d.id
            {limit_clause}
            """,
            params,
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = row_to_dict(row)
        item["company"] = COMPANY_NAME
        item["public_product_url"] = public_product_url(item.get("source_url") or "", item.get("product_id") or "")
        item["file_id"] = extract_file_id(item.get("pdf_url") or "")
        item["repair_status"] = "ready_for_browser_download" if item["public_product_url"] else "needs_manual_review"
        item["notes"] = (
            "Official PDF endpoint is retained, but plain HTTP fetch is blocked by Taiwan Life WAF."
            if item.get("pdf_url")
            else "No document URL found in legacy crawl."
        )
        items.append(item)
    return items


def build_report(items: list[dict[str, Any]], *, apply: bool, updated_products: int, updated_documents: int) -> dict[str, Any]:
    product_ids = {item["product_db_id"] for item in items}
    document_ids = {item["document_id"] for item in items if item.get("document_id")}
    public_urls = {item["public_product_url"] for item in items if item.get("public_product_url")}
    file_ids = {item["file_id"] for item in items if item.get("file_id")}

    return {
        "company": COMPANY_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "applied": apply,
        "summary": {
            "products_seen": len(product_ids),
            "documents_seen": len(document_ids),
            "public_product_urls": len(public_urls),
            "portal_file_ids": len(file_ids),
            "updated_products": updated_products,
            "updated_documents": updated_documents,
        },
        "status_meanings": {
            "browser_required": "The official URL exists, but this environment needs a browser-capable downloader to fetch it.",
            "needs_browser_download": "PDF text extraction is pending until a browser/TLS-compatible download step succeeds.",
        },
        "next_step": "Use a browser/TLS-capable downloader for each public_product_url and portal-api/File URL, then parse PDFs into chunks.",
        "items": items,
    }


def apply_repairs(items: list[dict[str, Any]]) -> tuple[int, int]:
    product_urls = {
        item["product_db_id"]: item["public_product_url"]
        for item in items
        if item.get("product_db_id") and item.get("public_product_url")
    }
    document_rows = [
        (item["document_id"], item.get("pdf_url") or "")
        for item in items
        if item.get("document_id") and item.get("pdf_url")
    ]

    with get_inventory_connection() as conn:
        for product_db_id, final_source_url in product_urls.items():
            conn.execute(
                """
                UPDATE insurance_products
                SET
                    final_source_url = ?,
                    url_status = 'browser_required',
                    document_status = 'browser_required',
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (final_source_url, product_db_id),
            )

        for document_id, pdf_url in document_rows:
            conn.execute(
                """
                UPDATE policy_documents
                SET
                    final_pdf_url = ?,
                    pdf_status = 'browser_required',
                    text_status = 'needs_browser_download',
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (pdf_url, document_id),
            )

    return len(product_urls), len(document_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair Taiwan Life legacy inventory URLs.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum document rows to inspect. 0 means all.")
    parser.add_argument("--apply", action="store_true", help="Write repaired statuses and public URLs back to inventory DB.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    items = collect_candidates(args.limit)
    updated_products = 0
    updated_documents = 0
    if args.apply:
        updated_products, updated_documents = apply_repairs(items)

    payload = build_report(
        items,
        apply=args.apply,
        updated_products=updated_products,
        updated_documents=updated_documents,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
