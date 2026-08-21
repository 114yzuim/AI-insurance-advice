"""
Collect Cathay Life public product pages and PDF documents.

The official category pages expose product detail links in server-rendered HTML.
Each detail page contains downloadable product terms and DM PDFs.
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
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from bs4 import BeautifulSoup
from inventory_db import get_inventory_connection

COMPANY_NAME = "\u570b\u6cf0\u4eba\u58fd"
BASE = "https://www.cathaylife.com.tw"
DEFAULT_OUTPUT = BACKEND / "data" / "cathay_life_adapter_report.json"

CATEGORIES = {
    "health-surgery": "\u5065\u5eb7\u91ab\u7642",
    "health-reimbursement-benefits": "\u5065\u5eb7\u91ab\u7642",
    "health-illness": "\u91cd\u5927\u75be\u75c5",
    "health-long-term-care": "\u9577\u7167",
    "accident": "\u610f\u5916\u50b7\u5bb3",
    "life-caring": "\u58fd\u96aa\u4fdd\u969c",
    "investment-va": "\u6295\u8cc7\u578b\u4fdd\u96aa",
    "savings-refund": "\u5132\u84c4\u9084\u672c",
    "travel": "\u65c5\u884c\u5e73\u5b89",
}

PRODUCT_HREF_RE = re.compile(
    r"/official/content/cathaylife-official/zh-tw/cathaylife/products/([^/]+)/([^/#?]+)(?:\.html)?$"
)


def get_company_id(conn) -> int | None:
    row = conn.execute(
        "SELECT id FROM insurance_companies WHERE short_name = ? OR name = ? LIMIT 1",
        (COMPANY_NAME, COMPANY_NAME),
    ).fetchone()
    return int(row["id"]) if row else None


def normalize_url(href: str) -> str:
    url = urljoin(BASE, href)
    parsed = urlparse(url)
    if parsed.path.endswith(".html"):
        url = url[: -len(".html")]
    return url


def product_id_from_url(url: str) -> str:
    segment = urlparse(url).path.rstrip("/").split("/")[-1]
    return segment.upper()


def document_type(label: str, href: str) -> str:
    if "\u689d\u6b3e" in label:
        return "terms"
    if "DM" in label.upper() or "\u7c21\u4ecb" in label:
        return "dm"
    if "pdf" in href.lower():
        return "pdf"
    return "document"


def fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def collect_product_links(client: httpx.Client, limit: int) -> list[dict[str, str]]:
    products: dict[str, dict[str, str]] = {}
    for slug, category in CATEGORIES.items():
        category_url = f"{BASE}/official/products/{slug}"
        html = fetch_html(client, category_url)
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            match = PRODUCT_HREF_RE.search(href)
            if not match:
                continue
            detail_category, _ = match.groups()
            detail_url = normalize_url(href)
            text = " ".join(anchor.get_text(" ", strip=True).split())
            products.setdefault(
                detail_url,
                {
                    "source_url": detail_url,
                    "category_url": category_url,
                    "category": CATEGORIES.get(detail_category, category),
                    "list_text": text,
                    "product_id": product_id_from_url(detail_url),
                },
            )
            if limit > 0 and len(products) >= limit:
                return list(products.values())
    return list(products.values())


def collect_product_detail(client: httpx.Client, product: dict[str, str]) -> dict[str, Any]:
    html = fetch_html(client, product["source_url"])
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = " ".join(h1.get_text(" ", strip=True).split())
    product_name = title or product.get("list_text") or product["product_id"]

    documents: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if "/content/dam/" not in href and "/-/media/" not in href and not href.lower().endswith(".pdf"):
            continue
        pdf_url = urljoin(BASE, href)
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)
        documents.append(
            {
                "document_type": document_type(label, href),
                "title": label or product_name,
                "pdf_url": pdf_url,
            }
        )

    stable_id = product["product_id"]
    if not re.search(r"[A-Z0-9]{2,}", stable_id):
        stable_id = hashlib.sha1(product["source_url"].encode("utf-8")).hexdigest()[:10].upper()

    return {
        "company": COMPANY_NAME,
        "product_id": stable_id,
        "product_name": product_name,
        "category": product["category"],
        "source_url": product["source_url"],
        "category_url": product["category_url"],
        "documents": documents,
    }


def collect(limit: int) -> list[dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True, verify=False) as client:
        products = collect_product_links(client, limit)
        return [collect_product_detail(client, product) for product in products]


def apply_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"products_upserted": 0, "documents_upserted": 0}
    with get_inventory_connection() as conn:
        company_id = get_company_id(conn)
        for item in items:
            conn.execute(
                """
                INSERT INTO insurance_products (
                    product_id, company_id, company_name, product_name, category, status,
                    source, source_url, final_source_url, url_status, document_status, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'active', 'official_adapter', ?, ?, 'ok', ?, ?, datetime('now'))
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
                    "ok" if item["documents"] else "missing",
                    json.dumps({"category_url": item["category_url"]}, ensure_ascii=False),
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
                    (
                        product_db_id,
                        doc["document_type"],
                        doc["title"],
                        doc["pdf_url"],
                        doc["pdf_url"],
                    ),
                )
                counts["documents_upserted"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Cathay Life product and PDF inventory.")
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
