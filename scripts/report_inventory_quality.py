import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection

DEFAULT_OUTPUT = BACKEND / "data" / "inventory_quality_report.json"


def rows(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def build_report(top: int) -> dict[str, Any]:
    with get_inventory_connection() as conn:
        totals = {
            "companies": conn.execute("SELECT COUNT(*) FROM insurance_companies").fetchone()[0],
            "products": conn.execute("SELECT COUNT(*) FROM insurance_products").fetchone()[0],
            "documents": conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0],
            "downloaded_documents": conn.execute("SELECT COUNT(*) FROM policy_documents WHERE local_path != ''").fetchone()[0],
        }
        by_company = rows(
            conn,
            """
            SELECT
                company_name,
                COUNT(*) AS products,
                SUM(CASE WHEN document_status = 'ok' THEN 1 ELSE 0 END) AS pdf_ok,
                SUM(CASE WHEN document_status = 'blocked' THEN 1 ELSE 0 END) AS pdf_blocked,
                SUM(CASE WHEN document_status = 'browser_required' THEN 1 ELSE 0 END) AS pdf_browser_required,
                SUM(CASE WHEN document_status = 'redirected' THEN 1 ELSE 0 END) AS pdf_redirected,
                SUM(CASE WHEN document_status = 'non_pdf' THEN 1 ELSE 0 END) AS pdf_non_pdf,
                SUM(CASE WHEN url_status = 'redirected' THEN 1 ELSE 0 END) AS source_redirected
            FROM insurance_products
            GROUP BY company_name
            ORDER BY products DESC
            """,
        )
        by_status = rows(
            conn,
            """
            SELECT url_status, document_status, COUNT(*) AS products
            FROM insurance_products
            GROUP BY url_status, document_status
            ORDER BY products DESC
            """,
        )
        duplicate_pdf_urls = rows(
            conn,
            """
            SELECT
                d.pdf_url,
                COUNT(DISTINCT p.id) AS product_count,
                GROUP_CONCAT(p.company_name || '|' || p.product_id || '|' || p.product_name, '\n') AS products
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE d.pdf_url != ''
            GROUP BY d.pdf_url
            HAVING COUNT(DISTINCT p.id) > 1
            ORDER BY product_count DESC
            LIMIT ?
            """,
            (top,),
        )
        duplicate_checksums = rows(
            conn,
            """
            SELECT
                d.checksum,
                COUNT(DISTINCT p.id) AS product_count,
                GROUP_CONCAT(p.company_name || '|' || p.product_id || '|' || p.product_name || '|' || d.local_path, '\n') AS products
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE d.checksum != ''
            GROUP BY d.checksum
            HAVING COUNT(DISTINCT p.id) > 1
            ORDER BY product_count DESC
            LIMIT ?
            """,
            (top,),
        )
        non_pdf_documents = rows(
            conn,
            """
            SELECT p.company_name, p.product_id, p.product_name, d.pdf_url, d.final_pdf_url, d.pdf_status
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE d.pdf_status = 'non_pdf'
            ORDER BY p.company_name, p.product_id
            LIMIT ?
            """,
            (top,),
        )
        browser_required_documents = rows(
            conn,
            """
            SELECT
                p.company_name,
                p.product_id,
                p.product_name,
                p.final_source_url,
                d.pdf_url,
                d.final_pdf_url,
                d.pdf_status,
                d.text_status
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE d.pdf_status = 'browser_required' OR d.text_status = 'needs_browser_download'
            ORDER BY p.company_name, p.product_id
            LIMIT ?
            """,
            (top,),
        )
        blocked_companies = rows(
            conn,
            """
            SELECT company_name, COUNT(*) AS blocked_products
            FROM insurance_products
            WHERE
                document_status IN ('blocked', 'browser_required')
                OR url_status IN ('blocked', 'browser_required')
            GROUP BY company_name
            ORDER BY blocked_products DESC
            """,
        )
        suspicious_terms = rows(
            conn,
            """
            SELECT p.company_name, p.product_id, p.product_name, d.pdf_url, d.final_pdf_url
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE
                lower(d.pdf_url) LIKE '%guide%'
                OR d.pdf_url LIKE '%導讀%'
                OR lower(d.final_pdf_url) LIKE '%guide%'
                OR d.final_pdf_url LIKE '%導讀%'
            ORDER BY p.company_name, p.product_id
            LIMIT ?
            """,
            (top,),
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "by_company": by_company,
        "by_status": by_status,
        "blocked_companies": blocked_companies,
        "duplicate_pdf_urls": duplicate_pdf_urls,
        "duplicate_checksums": duplicate_checksums,
        "non_pdf_documents": non_pdf_documents,
        "browser_required_documents": browser_required_documents,
        "suspicious_terms": suspicious_terms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate inventory quality report.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()
    report = build_report(args.top)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "totals": report["totals"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
