"""
Collect BNP Paribas Cardif Taiwan policy terms from the official terms page.

Cardif's product-category pages are rendered by Liferay, but the public
"契約條款" page exposes product names and PDF links as ordinary anchors.
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

COMPANY_NAME = "法國巴黎人壽"
BASE = "https://life.cardif.com.tw"
SOURCE_URL = f"{BASE}/a59"
DEFAULT_OUTPUT = BACKEND / "data" / "cardif_life_adapter_report.json"


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
    value = value.replace("\uf989", "黎").replace("\uf98e\uf90a", "年金")
    return re.sub(r"\s+", " ", value).strip()


def filename_for(url: str) -> str:
    for segment in reversed(urlparse(url).path.split("/")):
        if ".pdf" in segment.lower():
            return unquote(segment)
    return unquote(urlparse(url).path.rsplit("/", 1)[-1])


def product_id_from_url(pdf_url: str, product_name: str) -> str:
    filename = filename_for(pdf_url)
    stem = filename.split(".", 1)[0]
    stem = re.sub(r"(?i)(_?provision|_?clause|_?terms)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
    if stem:
        return f"CARDIF-{stem[:42]}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"CARDIF-{digest}"


def category_for(product_name: str) -> str:
    if "醫療" in product_name or "健康" in product_name or "癌" in product_name or "疾病" in product_name or "住院" in product_name:
        return "健康醫療"
    if "意外" in product_name or "傷害" in product_name:
        return "意外傷害"
    if "年金" in product_name:
        return "年金保險"
    if "投資" in product_name or "變額" in product_name or "萬能" in product_name:
        return "投資型保險"
    if "信用" in product_name or "貸" in product_name:
        return "信用保障"
    if "批註" in product_name or "約定" in product_name:
        return "批註條款"
    return "壽險保障"


def is_product_terms(label: str, href: str) -> bool:
    if ".pdf" not in href.lower():
        return False
    if not label.startswith("法商法國巴黎") and not label.startswith("法商法國巴"):
        return False
    filename = filename_for(href).lower()
    return "provision" in filename or "vie_" in filename or "ed_" in filename


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    try:
        response = httpx.get(SOURCE_URL, headers=headers, timeout=60, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        return [], [{"source_url": SOURCE_URL, "error": str(exc)[:240]}]

    soup = BeautifulSoup(response.text, "html.parser")
    items_by_id: dict[str, dict[str, Any]] = {}
    for anchor in soup.find_all("a", href=True):
        product_name = clean_text(anchor.get_text(" ", strip=True))
        pdf_url = urljoin(SOURCE_URL, anchor["href"])
        if not is_product_terms(product_name, pdf_url):
            continue
        stable_id = product_id_from_url(pdf_url, product_name)
        if stable_id in items_by_id:
            continue
        items_by_id[stable_id] = {
            "company": COMPANY_NAME,
            "product_id": stable_id,
            "product_name": product_name,
            "category": category_for(product_name),
            "status": "unknown",
            "is_historical": 0,
            "source_url": SOURCE_URL,
            "documents": [
                {
                    "document_type": "terms",
                    "title": f"{product_name} 契約條款",
                    "pdf_url": pdf_url,
                }
            ],
            "metadata": {
                "source": "official_contract_terms_page",
                "filename": filename_for(pdf_url),
            },
        }
        if limit > 0 and len(items_by_id) >= limit:
            break
    return list(items_by_id.values()), []


def apply_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"products_upserted": 0, "documents_upserted": 0}
    with get_inventory_connection() as conn:
        company_id = get_company_id(conn)
        for item in items:
            conn.execute(
                """
                INSERT INTO insurance_products (
                    product_id, company_id, company_name, product_name, category,
                    status, source, source_url, final_source_url, url_status, document_status,
                    is_historical, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'official_adapter', ?, ?, 'ok', 'ok', ?, ?, datetime('now'))
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
                    is_historical=excluded.is_historical,
                    metadata=excluded.metadata,
                    updated_at=datetime('now')
                """,
                (
                    item["product_id"],
                    company_id,
                    COMPANY_NAME,
                    item["product_name"],
                    item["category"],
                    item["status"],
                    item["source_url"],
                    item["source_url"],
                    item["is_historical"],
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
    parser = argparse.ArgumentParser(description="Collect BNP Paribas Cardif Taiwan contract terms.")
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
