"""
Collect Chunghwa Post simple life insurance products from official pages.

The active products are exposed as normal HTML detail pages with PDF product
DM links. Discontinued products are listed in a table with one official policy
terms PDF per row.
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

COMPANY_NAME = "中華郵政"
COMPANY_FULL_NAME = "中華郵政股份有限公司"
BASE = "https://www.post.gov.tw"
ACTIVE_URL = f"{BASE}/post/internet/Insurance/index.jsp?ID=4010102"
DISCONTINUED_URL = f"{BASE}/post/internet/Insurance/index.jsp?ID=4010101"
DEFAULT_OUTPUT = BACKEND / "data" / "post_life_adapter_report.json"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_product_name(value: str) -> tuple[str, str]:
    value = clean_text(value)
    match = re.search(r"（本險種自(.+?)停止銷售）", value)
    discontinue_date = match.group(1) if match else ""
    name = re.sub(r"（本險種自.+?停止銷售）", "", value)
    return clean_text(name), discontinue_date


def category_for(product_name: str, source_category: str = "") -> str:
    text = f"{source_category} {product_name}"
    if "醫療" in text or "健康" in text or "住院" in text or "癌" in text or "疾病" in text:
        return "健康醫療"
    if "意外" in text or "傷害" in text:
        return "意外傷害"
    if "年金" in text:
        return "年金保險"
    if "還本" in text or "增額" in text or "儲蓄" in text or "利率" in text:
        return "儲蓄還本"
    return "壽險保障"


def product_id(prefix: str, raw_key: str, product_name: str) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "-", raw_key).strip("-").upper()
    if key:
        return f"POST-{prefix}-{key[:36]}"
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:12].upper()
    return f"POST-{prefix}-{digest}"


def normalized_href(page_url: str, href: str) -> str:
    if href.strip().lower().startswith(("javascript:", "mailto:", "tel:")):
        return ""
    return urljoin(page_url, href)


def ensure_company(conn) -> int:
    conn.execute(
        """
        INSERT INTO insurance_companies (
            slug, name, short_name, type, status, former_names, official_url, source_url, updated_at
        )
        VALUES (
            'chunghwa-post-life', ?, ?, 'life', 'active', '[]', ?, ?, datetime('now')
        )
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name,
            short_name=excluded.short_name,
            type=excluded.type,
            status=excluded.status,
            official_url=excluded.official_url,
            source_url=excluded.source_url,
            updated_at=datetime('now')
        """,
        (COMPANY_FULL_NAME, COMPANY_NAME, BASE, ACTIVE_URL),
    )
    row = conn.execute(
        "SELECT id FROM insurance_companies WHERE slug = 'chunghwa-post-life'"
    ).fetchone()
    return int(row["id"])


def get(client: httpx.Client, url: str) -> BeautifulSoup:
    response = client.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def collect_active(client: httpx.Client, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    items_by_url: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    queue = [ACTIVE_URL]
    seen_pages: set[str] = set()
    detail_urls: set[str] = set()

    while queue:
        page_url = queue.pop(0)
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        try:
            soup = get(client, page_url)
        except Exception as exc:
            errors.append({"source_url": page_url, "error": str(exc)[:240]})
            continue
        for anchor in soup.find_all("a", href=True):
            href = normalized_href(page_url, anchor["href"])
            if not href:
                continue
            if "ID=4010102" not in href:
                continue
            if "page_type=3" in href and "IP_ID=" in href:
                detail_urls.add(href)
            elif "page_type=2" in href and href not in seen_pages:
                queue.append(href)

    for detail_url in sorted(detail_urls):
        if limit > 0 and len(items_by_url) >= limit:
            break
        try:
            soup = get(client, detail_url)
        except Exception as exc:
            errors.append({"source_url": detail_url, "error": str(exc)[:240]})
            continue
        text = soup.get_text(" ", strip=True)
        title_match = re.search(
            r"回列表\s+(?:若Javascript不支援時.+?回上頁\s+)?(.+?)\s+自\d{2,3}年\d{1,2}月\d{1,2}日起發售",
            text,
        )
        product_name = clean_text(title_match.group(1)) if title_match else ""
        if not product_name:
            heading = soup.select_one("h1, h2, h3, .title, .page-title")
            product_name = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        if not product_name:
            errors.append({"source_url": detail_url, "error": "missing product name"})
            continue

        parsed = urlparse(detail_url)
        ip_id = parse_qs(parsed.query).get("IP_ID", [""])[0]
        docs: list[dict[str, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = normalized_href(detail_url, anchor["href"])
            if not href:
                continue
            label = clean_text(anchor.get_text(" ", strip=True))
            if ".pdf" not in href.lower():
                continue
            if label in {"商品DM"} or "IP_URL" in href:
                docs.append({"document_type": "dm", "title": f"{product_name} 商品DM", "pdf_url": href})

        sale_date_match = re.search(r"自(\d{2,3}年\d{1,2}月\d{1,2}日)起發售", text)
        items_by_url[detail_url] = {
            "company": COMPANY_NAME,
            "product_id": product_id("ACTIVE", ip_id, product_name),
            "product_name": product_name,
            "category": category_for(product_name),
            "status": "active",
            "is_historical": 0,
            "source_url": detail_url,
            "documents": docs,
            "metadata": {
                "source": "official_active_product_pages",
                "ip_id": ip_id,
                "sale_date": sale_date_match.group(1) if sale_date_match else "",
                "source_page_count": len(seen_pages),
            },
        }
    return list(items_by_url.values()), errors


def collect_discontinued(client: httpx.Client, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        soup = get(client, DISCONTINUED_URL)
    except Exception as exc:
        return [], [{"source_url": DISCONTINUED_URL, "error": str(exc)[:240]}]

    current_type = ""
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            cell_texts = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
            if cell_texts[0] == "商品類型":
                continue
            pdf_anchor = tr.find("a", href=True)
            if not pdf_anchor:
                continue
            if len(cells) >= 3:
                current_type = cell_texts[0] or current_type
                raw_name = cell_texts[1]
            else:
                raw_name = cell_texts[0]
            product_name, discontinue_date = normalize_product_name(raw_name)
            if not product_name:
                continue
            pdf_url = normalized_href(DISCONTINUED_URL, pdf_anchor["href"])
            if not pdf_url:
                continue
            items.append(
                {
                    "company": COMPANY_NAME,
                    "product_id": product_id("OLD", pdf_url.rsplit("/", 1)[-1], product_name),
                    "product_name": product_name,
                    "category": category_for(product_name, current_type),
                    "status": "discontinued",
                    "is_historical": 1,
                    "source_url": DISCONTINUED_URL,
                    "documents": [
                        {
                            "document_type": "terms",
                            "title": f"{product_name} 保單條款",
                            "pdf_url": pdf_url,
                        }
                    ],
                    "metadata": {
                        "source": "official_discontinued_terms_table",
                        "product_type": current_type,
                        "discontinue_date": discontinue_date,
                    },
                }
            )
            if limit > 0 and len(items) >= limit:
                return items, errors
    return items, errors


def collect(limit: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    with httpx.Client(headers=headers, timeout=45, follow_redirects=True, verify=False) as client:
        active, active_errors = collect_active(client, limit)
        remaining = 0 if limit == 0 else max(limit - len(active), 0)
        discontinued, discontinued_errors = collect_discontinued(client, remaining)
    items = active + discontinued
    return items[:limit] if limit > 0 else items, active_errors + discontinued_errors


def apply_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"products_upserted": 0, "documents_upserted": 0}
    with get_inventory_connection() as conn:
        company_id = ensure_company(conn)
        for item in items:
            document_status = "ok" if item["documents"] else "missing_terms"
            conn.execute(
                """
                INSERT INTO insurance_products (
                    product_id, company_id, company_name, product_name, category,
                    status, source, source_url, final_source_url, url_status, document_status,
                    is_historical, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'official_adapter', ?, ?, 'ok', ?, ?, ?, datetime('now'))
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
                    document_status,
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
    parser = argparse.ArgumentParser(description="Collect Chunghwa Post life product inventory.")
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
            "active_products": sum(1 for item in items if item["status"] == "active"),
            "discontinued_products": sum(1 for item in items if item["status"] == "discontinued"),
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
