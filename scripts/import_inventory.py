import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection, init_inventory_db

DEFAULT_COMPANIES = BACKEND / "data" / "insurance_companies_seed.json"
DEFAULT_PRODUCTS = BACKEND / "data" / "crawled_products_with_pdf_dm_links.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_companies(path: Path) -> int:
    data = load_json(path)
    companies = data.get("companies", [])
    with get_inventory_connection() as conn:
        for company in companies:
            conn.execute(
                """
                INSERT INTO insurance_companies (
                    slug, name, short_name, type, status, former_names, official_url, source_url, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(slug) DO UPDATE SET
                    name=excluded.name,
                    short_name=excluded.short_name,
                    type=excluded.type,
                    status=excluded.status,
                    former_names=excluded.former_names,
                    official_url=excluded.official_url,
                    source_url=excluded.source_url,
                    updated_at=datetime('now')
                """,
                (
                    company["slug"],
                    company["name"],
                    company["short_name"],
                    company["type"],
                    company.get("status", "active"),
                    json.dumps(company.get("former_names", []), ensure_ascii=False),
                    company.get("official_url", ""),
                    company.get("source_url", data.get("source_url", "")),
                ),
            )
    return len(companies)


def company_id_for(conn, company_name: str) -> int | None:
    row = conn.execute(
        """
        SELECT id
        FROM insurance_companies
        WHERE short_name = ?
           OR name = ?
           OR EXISTS (
                SELECT 1 FROM json_each(insurance_companies.former_names)
                WHERE json_each.value = ?
           )
        LIMIT 1
        """,
        (company_name, company_name, company_name),
    ).fetchone()
    return int(row["id"]) if row else None


def import_products(path: Path) -> int:
    data = load_json(path)
    products = data.get("products", [])
    with get_inventory_connection() as conn:
        for product in products:
            company_name = product.get("company", "").strip()
            company_id = company_id_for(conn, company_name)
            download_urls = product.get("download_urls") or []
            metadata = {
                "download_links_raw": product.get("download_links_raw", ""),
                "raw_source_file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            }
            conn.execute(
                """
                INSERT INTO insurance_products (
                    product_id, company_id, company_name, product_name, category, currency,
                    status, source, source_url, metadata, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'unknown', 'existing_crawl', ?, ?, datetime('now'))
                ON CONFLICT(product_id, company_name) DO UPDATE SET
                    company_id=excluded.company_id,
                    product_name=excluded.product_name,
                    category=excluded.category,
                    currency=excluded.currency,
                    source_url=excluded.source_url,
                    metadata=excluded.metadata,
                    updated_at=datetime('now')
                """,
                (
                    product.get("product_id", ""),
                    company_id,
                    company_name,
                    product.get("product_name", ""),
                    product.get("category", "其他"),
                    product.get("currency", ""),
                    product.get("source_url", ""),
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            product_db_id = conn.execute(
                "SELECT id FROM insurance_products WHERE product_id = ? AND company_name = ?",
                (product.get("product_id", ""), company_name),
            ).fetchone()["id"]
            for url in download_urls:
                if not url:
                    continue
                conn.execute(
                    """
                    INSERT INTO policy_documents (product_db_id, document_type, title, pdf_url, updated_at)
                    VALUES (?, 'terms', ?, ?, datetime('now'))
                    ON CONFLICT(product_db_id, pdf_url) DO UPDATE SET
                        title=excluded.title,
                        updated_at=datetime('now')
                    """,
                    (product_db_id, product.get("product_name", ""), url),
                )
    return len(products)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed insurance company and product inventory tables.")
    parser.add_argument("--companies", type=Path, default=DEFAULT_COMPANIES)
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS)
    parser.add_argument("--skip-companies", action="store_true")
    parser.add_argument("--skip-products", action="store_true")
    args = parser.parse_args()

    init_inventory_db()
    company_count = 0 if args.skip_companies else seed_companies(args.companies)
    product_count = 0 if args.skip_products else import_products(args.products)
    print(json.dumps({"companies": company_count, "products": product_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
