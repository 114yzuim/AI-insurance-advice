"""Phase 3: turn source_product_records into product_families / product_versions.

Scope, on purpose
------------------
- Matching is rule-based string normalization only (see
  inventory_repository.normalize_company_name / normalize_product_name) --
  no LLM, no embeddings. Two records are "the same family" only if their
  normalized (company, product name) keys are byte-identical.
- Only TII is populated as a real source right now. With a single source,
  every family trivially has "only TII" data -- that isn't a reconciliation
  finding, it's just the current state of the world, so this script does not
  write TII_ONLY (or any other) reconciliation_findings rows yet. It only
  reports, via the summary, how many families already have 2+ distinct
  sources (today: expected to be 0) -- that count is the trigger for when
  writing real findings starts being meaningful, which is future work.
- `reconciliation_findings.grace_until` and the whole RECENT_PENDING /
  15-business-day logic are intentionally NOT implemented here. The column
  exists (0002_market_universe.sql) so a later pass can fill it in once
  there's a second source to actually be "recent" or "pending" relative to.

What it does do
-----------------
For every source_product_records row (across all sources -- this is the one
script in the repo that reads all of them together, which is why it logs
its own crawl_runs entry under the synthetic "reconciliation" source rather
than any single real one):

  1. Skip records with an empty company_name or product_name (can't safely
     key a family on nothing) -- these are counted, not silently dropped.
  2. Upsert a product_families row for (company_name, product_name).
  3. Upsert a product_versions row keyed on that source record (one version
     per source record for now -- see inventory_repository's module note).
  4. Point that record's document_registry rows at the resulting version.

Usage:
    python scripts/reconcile_source_records.py
    python scripts/reconcile_source_records.py --source tii
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from inventory_db import get_inventory_connection  # noqa: E402
import inventory_repository as repo  # noqa: E402

_VERSION_FIELD_COLUMNS = (
    "product_code",
    "insurance_category",
    "insurance_type",
    "sale_start_date",
    "sale_end_date",
    "approval_date",
    "approval_number",
    "filing_number",
    "review_method",
)


def _fetch_source_records(conn, source_code: str | None) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if source_code:
        where = "WHERE s.code = ?"
        params.append(source_code)
    sql = f"""
        SELECT spr.id, spr.company_name, spr.product_name, {', '.join('spr.' + c for c in _VERSION_FIELD_COLUMNS)}
        FROM source_product_records spr
        JOIN inventory_sources s ON s.id = spr.source_id
        {where}
        ORDER BY spr.id
    """
    # conn.row_factory is sqlite3.Row (set by get_inventory_connection), which
    # still unpacks positionally like a plain tuple, so this works unchanged.
    columns = ["id", "company_name", "product_name", *_VERSION_FIELD_COLUMNS]
    rows = conn.execute(sql, params).fetchall()
    return [dict(zip(columns, row)) for row in rows]


def run(source_code: str | None) -> dict[str, Any]:
    stats = {
        "records_seen": 0,
        "skipped_missing_fields": 0,
        "families_created": 0,
        "families_existing": 0,
        "versions_created": 0,
        "versions_updated": 0,
        "versions_unchanged": 0,
        "documents_linked": 0,
    }

    with get_inventory_connection() as conn:
        repo.ensure_default_sources(conn)
        crawl_run_id = repo.create_crawl_run(
            conn, "reconciliation", "reconcile", metadata={"source_filter": source_code or "all"}
        )

        records = _fetch_source_records(conn, source_code)
        touched_family_ids: set[int] = set()

        for record in records:
            stats["records_seen"] += 1
            company_name = (record["company_name"] or "").strip()
            product_name = (record["product_name"] or "").strip()
            if not company_name or not product_name:
                stats["skipped_missing_fields"] += 1
                continue

            family_id, family_created = repo.upsert_product_family(conn, company_name, product_name)
            stats["families_created" if family_created else "families_existing"] += 1
            touched_family_ids.add(family_id)

            version_fields = {
                "canonical_company_name": company_name,
                "canonical_product_name": product_name,
                "version_label": record.get("approval_number") or record.get("sale_start_date") or "",
                **{col: record.get(col) for col in _VERSION_FIELD_COLUMNS},
            }
            version_id, version_status = repo.upsert_product_version(
                conn, record["id"], family_id, version_fields
            )
            stats[f"versions_{version_status}"] += 1

            stats["documents_linked"] += repo.link_documents_to_product_version(
                conn, record["id"], version_id
            )

        families_with_multiple_sources = sum(
            1 for family_id in touched_family_ids if repo.count_distinct_sources_in_family(conn, family_id) >= 2
        )
        stats["families_touched"] = len(touched_family_ids)
        stats["families_with_multiple_sources"] = families_with_multiple_sources

        repo.finish_crawl_run(
            conn,
            crawl_run_id,
            status="succeeded",
            records_seen=stats["records_seen"],
            records_changed=stats["versions_created"] + stats["versions_updated"],
        )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="Only reconcile records from this inventory_sources.code (default: all)")
    args = parser.parse_args()

    stats = run(args.source)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats["families_with_multiple_sources"] == 0:
        print(
            "\nNo family has 2+ distinct sources yet, so no reconciliation_findings "
            "were written -- see this script's module docstring for why.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
