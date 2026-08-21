"""
KGI Life repair adapter draft.

Current generic audit result:
- Many products point to a repeated `reading-friendly-user-guide__v7.pdf`.
- Product pages may still exist, but the existing crawl likely captured a guide PDF instead of the actual policy terms.

This draft identifies suspicious KGI mappings and emits a review report. It does not mutate the inventory DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection


def collect_suspicious(limit: int) -> list[dict]:
    with get_inventory_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.product_id, p.product_name, p.source_url, d.pdf_url, d.final_pdf_url
            FROM insurance_products p
            JOIN policy_documents d ON d.product_db_id = p.id
            WHERE p.company_name = '凱基人壽'
              AND (
                lower(d.pdf_url) LIKE '%guide%'
                OR lower(d.final_pdf_url) LIKE '%guide%'
                OR d.pdf_url LIKE '%導讀%'
                OR d.final_pdf_url LIKE '%導讀%'
                OR lower(d.pdf_url) LIKE '%reading-friendly%'
                OR lower(d.final_pdf_url) LIKE '%reading-friendly%'
              )
            ORDER BY p.product_id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft KGI Life suspicious PDF mapping report.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", type=Path, default=BACKEND / "data" / "kgi_life_suspicious_documents.json")
    args = parser.parse_args()
    payload = {
        "company": "凱基人壽",
        "status": "draft",
        "issue": "Some products appear to be mapped to a reading-friendly guide PDF rather than actual terms.",
        "items": collect_suspicious(args.limit),
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "items": len(payload["items"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
