"""
Export a deployable inventory seed from the local SQLite database.

The production SQLite file is intentionally git-ignored because it is large.
This script exports the tables Railway needs for product inventory dashboards
and clause search into a compressed JSON seed that can be committed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "insurance_inventory.db"
DEFAULT_OUTPUT = ROOT / "backend" / "data" / "inventory_seed.json.gz"
TABLES = ("insurance_companies", "insurance_products", "policy_documents", "policy_document_chunks")


def rows_for(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = []
    for row in conn.execute(f"SELECT * FROM {table}"):
        item = dict(row)
        if table == "policy_documents":
            item["parsed_text"] = ""
        rows.append(item)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compressed inventory seed for deployment.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        payload = {
            "meta": {
                "version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": str(args.db),
                "omitted_policy_document_parsed_text": True,
            },
            **{table: rows_for(conn, table) for table in TABLES},
        }
    finally:
        conn.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8") as seed_file:
        json.dump(payload, seed_file, ensure_ascii=False, separators=(",", ":"))

    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
                "tables": {table: len(payload[table]) for table in TABLES},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
