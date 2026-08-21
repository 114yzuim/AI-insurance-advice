"""
Collect TCB Life product documents from the official sitemap.

The TCB Life site is an SPA, but its sitemap exposes product URLs and PDF
assets. This adapter conservatively links PDFs to products when the product
code appears as a filename token.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from bs4 import BeautifulSoup
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u5408\u4f5c\u91d1\u5eab\u4eba\u58fd"
BASE = "https://my.tcb-life.com.tw"
SITEMAP_URL = f"{BASE}/sitemap.xml"
DEFAULT_OUTPUT = BACKEND / "data" / "tcb_life_adapter_report.json"


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


def fetch_sitemap(client: httpx.Client) -> list[str]:
    response = client.get(SITEMAP_URL)
    response.raise_for_status()
    return [html.unescape(loc) for loc in re.findall(r"<loc>(.*?)</loc>", response.text)]


def product_code_from_url(url: str) -> str | None:
    match = re.search(r"/product/([^/?#]+)", url)
    return unquote(match.group(1)).upper() if match else None


def filename_for(url: str) -> str:
    return unquote(urlparse(url).path.rsplit("/", 1)[-1])


def code_in_filename(code: str, filename: str) -> bool:
    return re.search(rf"(?i)(^|[^A-Z0-9]){re.escape(code)}([^A-Z0-9]|$)", filename) is not None


def document_type_for(filename: str) -> str:
    upper = filename.upper()
    if "\u689d\u6b3e" in filename or "PROVISION" in upper:
        return "terms"
    if "DM" in upper:
        return "dm"
    if "\u5546\u8aaa\u66f8" in filename or "\u91cd\u8981\u8aaa\u660e" in filename:
        return "brochure"
    return "supporting"


def category_for(keywords: str, product_name: str) -> str:
    text = f"{keywords} {product_name}"
    if "\u610f\u5916" in text or "\u50b7\u5bb3" in text:
        return "\u610f\u5916\u50b7\u5bb3"
    if "\u91ab\u7642" in text or "\u5065\u5eb7" in text or "\u764c" in text or "\u75c5" in text:
        return "\u5065\u5eb7\u91ab\u7642"
    if "\u5e74\u91d1" in text:
        return "\u5e74\u91d1\u4fdd\u96aa"
    if "\u6295\u8cc7" in text:
        return "\u6295\u8cc7\u578b\u4fdd\u96aa"
    return "\u58fd\u96aa\u4fdd\u969c"


def product_meta(client: httpx.Client, product_url: str, code: str) -> dict[str, str]:
    response = client.get(product_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    metas = {
        meta.get("name") or meta.get("property"): meta.get("content")
        for meta in soup.find_all("meta")
        if meta.get("content")
    }
    title = metas.get("title") or metas.get("og:title") or code
    product_name = clean_text(title.split("\uff5c", 1)[0])
    keywords = clean_text(metas.get("keywords") or "")
    description = clean_text(metas.get("description") or metas.get("og:description") or "")
    return {
        "product_name": product_name,
        "category": category_for(keywords, product_name),
        "keywords": keywords,
        "description": description,
    }


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    errors: list[dict[str, str]] = []
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True, verify=False) as client:
        locs = fetch_sitemap(client)
        product_urls = sorted({loc for loc in locs if product_code_from_url(loc)})
        pdf_urls = sorted({loc for loc in locs if unquote(loc).lower().endswith(".pdf")})
        items: list[dict[str, Any]] = []
        for product_url in product_urls:
            code = product_code_from_url(product_url)
            if not code:
                continue
            matches = [
                pdf_url
                for pdf_url in pdf_urls
                if code_in_filename(code, filename_for(pdf_url))
            ]
            if not matches:
                continue
            try:
                meta = product_meta(client, product_url, code)
            except Exception as exc:
                errors.append({"source_url": product_url, "error": str(exc)[:240]})
                meta = {"product_name": code, "category": "\u672a\u5206\u985e", "keywords": "", "description": ""}
            documents = [
                {
                    "document_type": document_type_for(filename_for(pdf_url)),
                    "title": filename_for(pdf_url).removesuffix(".pdf"),
                    "pdf_url": pdf_url,
                }
                for pdf_url in matches
            ]
            items.append(
                {
                    "company": COMPANY_NAME,
                    "product_id": f"TCB-{code}",
                    "product_name": meta["product_name"],
                    "category": meta["category"],
                    "source_url": product_url,
                    "documents": documents,
                    "metadata": {
                        "code": code,
                        "keywords": meta["keywords"],
                        "description": meta["description"],
                        "source": "sitemap",
                    },
                }
            )
            if limit > 0 and len(items) >= limit:
                break
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
    parser = argparse.ArgumentParser(description="Collect TCB Life product documents from official sitemap.")
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
