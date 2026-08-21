import json
from pathlib import Path
from functools import lru_cache
from inventory_db import get_inventory_connection, row_to_dict

DATA_PATH = Path(__file__).parent.parent / "data" / "crawled_products_with_pdf_dm_links.json"


@lru_cache(maxsize=1)
def get_products() -> list[dict]:
    inventory_products = get_inventory_products()
    if inventory_products:
        return inventory_products
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def get_inventory_products() -> list[dict]:
    try:
        with get_inventory_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.product_id, p.product_name, p.company_name AS company, p.category, p.currency,
                    p.source_url, p.final_source_url, p.status, p.url_status, p.document_status,
                    COALESCE(
                        json_group_array(d.pdf_url) FILTER (WHERE d.pdf_url IS NOT NULL),
                        '[]'
                    ) AS download_urls
                FROM insurance_products p
                LEFT JOIN policy_documents d ON d.product_db_id = p.id
                GROUP BY p.id
                ORDER BY p.company_name, p.product_name
                """
            ).fetchall()
        return [row_to_dict(row) for row in rows]
    except Exception:
        return []


def search_products(
    category: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = get_products()
    if category:
        results = [p for p in results if p["category"] == category]
    if company:
        results = [p for p in results if p["company"] == company]
    if keyword:
        kw = keyword.lower()
        results = [
            p for p in results
            if kw in p["product_name"].lower() or kw in p.get("company", "").lower()
        ]
    return results


def get_product_inventory_summary() -> dict:
    with get_inventory_connection() as conn:
        product_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_products").fetchone()["c"]
        company_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_companies").fetchone()["c"]
        document_count = conn.execute("SELECT COUNT(*) AS c FROM policy_documents").fetchone()["c"]
        by_company = [
            dict(row)
            for row in conn.execute(
                """
                SELECT company_name AS company, COUNT(*) AS count
                FROM insurance_products
                GROUP BY company_name
                ORDER BY count DESC, company_name
                """
            ).fetchall()
        ]
        by_audit = [
            dict(row)
            for row in conn.execute(
                """
                SELECT url_status, document_status, COUNT(*) AS count
                FROM insurance_products
                GROUP BY url_status, document_status
                ORDER BY count DESC
                """
            ).fetchall()
        ]
    return {
        "companies": company_count,
        "products": product_count,
        "documents": document_count,
        "by_company": by_company,
        "by_audit": by_audit,
    }
