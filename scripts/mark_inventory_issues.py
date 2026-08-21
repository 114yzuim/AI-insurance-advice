import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection


def main() -> None:
    updates = {
        "kgi_suspicious_guide": 0,
        "taiwan_browser_required": 0,
        "yuanta_browser_required": 0,
        "fubon_redirected": 0,
        "shinkong_non_pdf": 0,
    }
    with get_inventory_connection() as conn:
        rows = conn.execute(
            """
            SELECT d.id
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE p.company_name = '凱基人壽'
              AND (
                lower(COALESCE(d.final_pdf_url, d.pdf_url)) LIKE '%guide%'
                OR lower(COALESCE(d.final_pdf_url, d.pdf_url)) LIKE '%reading-friendly%'
                OR COALESCE(d.final_pdf_url, d.pdf_url) LIKE '%導讀%'
              )
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE policy_documents SET text_status = 'needs_review', updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            updates["kgi_suspicious_guide"] += 1

        rows = conn.execute(
            """
            SELECT d.id
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE p.company_name = '台灣人壽'
              AND d.pdf_status IN ('non_pdf', 'blocked', 'browser_required')
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                UPDATE policy_documents
                SET
                    pdf_status = 'browser_required',
                    text_status = 'needs_browser_download',
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (row["id"],),
            )
            updates["taiwan_browser_required"] += 1

        rows = conn.execute(
            """
            SELECT d.id
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE p.company_name = '元大人壽'
              AND (d.local_path = '' OR d.local_path IS NULL)
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                UPDATE policy_documents
                SET
                    pdf_status = 'browser_required',
                    text_status = 'needs_browser_download',
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (row["id"],),
            )
            updates["yuanta_browser_required"] += 1

        rows = conn.execute(
            """
            SELECT d.id
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE p.company_name = '富邦人壽' AND d.pdf_status = 'redirected'
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE policy_documents SET text_status = 'needs_redirect_review', updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            updates["fubon_redirected"] += 1

        rows = conn.execute(
            """
            SELECT d.id
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE p.company_name = '新光人壽' AND d.pdf_status = 'non_pdf'
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE policy_documents SET text_status = 'needs_url_repair', updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            updates["shinkong_non_pdf"] += 1

    print(json.dumps(updates, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
