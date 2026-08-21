"""
Collect Chubb Life Taiwan product prospectuses from official pages.

Chubb publishes investment product prospectuses as paragraphs where the
product name surrounds a PDF download link. The adapter intentionally skips
site-wide forms and friendly-reading instructions.
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

COMPANY_NAME = "\u5b89\u9054\u4eba\u58fd"
BASE = "https://life.chubb.com"
SOURCE_URLS = {
    f"{BASE}/tw-zh/products/investing/prospectus.html": "\u6295\u8cc7\u578b\u5546\u54c1\u8aaa\u660e\u66f8",
}
DEFAULT_OUTPUT = BACKEND / "data" / "chubb_life_adapter_report.json"
SKIP_KEYWORDS = (
    "\u53cb\u5584\u95b1\u8b80",
    "\u4f7f\u7528\u8aaa\u660e",
    "\u6295\u8cc7\u6a19\u7684",
)


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
    stem = re.sub(r"[^A-Za-z0-9]+", "-", filename_for(pdf_url).split(".", 1)[0]).strip("-").upper()
    if stem:
        return f"CHUBB-{stem[:42]}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"CHUBB-{digest}"


def product_name_from_paragraph(text: str) -> str:
    text = re.sub(r"\s*\(?\s*\u4e0b\u8f09\s*\)?\s*", "", text)
    text = text.replace("\u5546\u54c1\u8aaa\u660e\u66f8", "")
    return clean_text(text)


def category_for(product_name: str) -> str:
    if "\u5e74\u91d1" in product_name:
        return "\u5e74\u91d1\u4fdd\u96aa"
    if "\u8b8a\u984d" in product_name or "\u6295\u8cc7" in product_name:
        return "\u6295\u8cc7\u578b\u4fdd\u96aa"
    if "\u610f\u5916" in product_name or "\u50b7\u5bb3" in product_name:
        return "\u610f\u5916\u50b7\u5bb3"
    if "\u91ab\u7642" in product_name or "\u5065\u5eb7" in product_name or "\u764c" in product_name:
        return "\u5065\u5eb7\u91ab\u7642"
    return "\u58fd\u96aa\u4fdd\u969c"


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[dict[str, str]] = []
    with httpx.Client(headers=headers, timeout=45, follow_redirects=True) as client:
        for source_url, section in SOURCE_URLS.items():
            try:
                response = client.get(source_url)
                response.raise_for_status()
            except Exception as exc:
                errors.append({"source_url": source_url, "error": str(exc)[:240]})
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                pdf_url = urljoin(source_url, anchor["href"])
                if ".pdf" not in pdf_url.lower() or "prospectus" not in pdf_url.lower():
                    continue
                paragraph = anchor.find_parent("p")
                text = clean_text(paragraph.get_text(" ", strip=True) if paragraph else "")
                if "\u5546\u54c1\u8aaa\u660e\u66f8" not in text or COMPANY_NAME not in text:
                    continue
                if any(keyword in text for keyword in SKIP_KEYWORDS):
                    continue
                product_name = product_name_from_paragraph(text)
                if not product_name.startswith(COMPANY_NAME):
                    continue
                product_id = product_id_from_url(pdf_url, product_name)
                if product_id in seen:
                    continue
                seen.add(product_id)
                items.append(
                    {
                        "company": COMPANY_NAME,
                        "product_id": product_id,
                        "product_name": product_name,
                        "category": category_for(product_name),
                        "source_url": source_url,
                        "documents": [
                            {
                                "document_type": "brochure",
                                "title": f"{product_name} \u5546\u54c1\u8aaa\u660e\u66f8",
                                "pdf_url": pdf_url,
                            }
                        ],
                        "metadata": {
                            "source_section": section,
                            "source": "official_prospectus_page",
                            "filename": filename_for(pdf_url),
                        },
                    }
                )
                if limit > 0 and len(items) >= limit:
                    return items[:limit], errors
    return items, errors


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
    parser = argparse.ArgumentParser(description="Collect Chubb Life Taiwan product prospectuses.")
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
