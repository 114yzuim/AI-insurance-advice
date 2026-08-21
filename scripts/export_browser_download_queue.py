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

from inventory_db import get_inventory_connection, row_to_dict

DEFAULT_OUTPUT = BACKEND / "data" / "browser_required_download_queue.json"


def fetch_items(company: str | None) -> list[dict[str, Any]]:
    where = [
        "(d.pdf_status = 'browser_required' OR d.text_status = 'needs_browser_download')",
        "(d.local_path = '' OR d.local_path IS NULL)",
    ]
    params: list[Any] = []
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    with get_inventory_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT
                d.id AS document_id,
                p.company_name,
                p.product_id,
                p.product_name,
                p.final_source_url,
                p.source_url,
                d.document_type,
                d.title AS document_title,
                d.pdf_url,
                d.final_pdf_url,
                d.pdf_status,
                d.text_status
            FROM policy_documents d
            JOIN insurance_products p ON p.id = d.product_db_id
            WHERE {' AND '.join(where)}
            ORDER BY p.company_name, p.product_id, d.id
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export documents that need browser/manual PDF download.")
    parser.add_argument("--company")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    items = fetch_items(args.company)
    by_company: dict[str, int] = {}
    for item in items:
        by_company[item["company_name"]] = by_company.get(item["company_name"], 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "by_company": by_company,
        "instructions": [
            "Open final_source_url first when available, then download final_pdf_url/pdf_url with a real browser session.",
            "After PDFs are placed under backend/data/documents, update policy_documents.local_path/checksum/pdf_status and rerun parse_pdf_snapshots.py.",
        ],
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "total": len(items), "by_company": by_company}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
