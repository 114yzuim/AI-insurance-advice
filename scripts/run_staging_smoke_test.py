"""Staging smoke test -- a bounded, read-only/dry-run pass over the
CURRENT database (or one --company-uid), meant to run right before pointing
a Railway staging deploy at real traffic.

This deliberately does NOT crawl anything -- no IB/TII requests, no
CAPTCHA, no WAF interaction. It only exercises the pipeline's *processing*
stages (migrations, object storage, parsers, readiness) against whatever is
already in the database, in dry-run mode wherever a script supports one, so
running this on staging is always safe to repeat and never mutates
anything by itself except where explicitly noted below.

What actually writes vs. what's dry-run, so this is never a surprise:
  - migration check         : read-only (a fresh `get_inventory_connection()`
                               DOES apply any pending migration on connect --
                               same as every other script in this project;
                               this is the one place this smoke test can
                               change the DB, and only by adding schema, not
                               data)
  - object store backfill    : --dry-run always
  - document parser          : --dry-run always
  - readiness report          : read-only
  - deployment readiness check: read-only

Usage:
    python scripts/run_staging_smoke_test.py
    python scripts/run_staging_smoke_test.py --company-uid 03557115 --limit 20
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
import backfill_document_snapshots_to_object_store as backfill_mod  # noqa: E402
import parse_document_snapshots  # noqa: E402
import check_deployment_readiness  # noqa: E402
from report_policy_data_readiness import build_report as build_readiness_report  # noqa: E402


def _step_migration_check(conn) -> dict[str, Any]:
    # get_inventory_connection() (called by the caller before this runs)
    # already applied any pending migration on connect -- this step just
    # reports the resulting state, matching check_deployment_readiness.py's
    # own check so this smoke test's summary and that checker never
    # disagree about migration status.
    return check_deployment_readiness.check_migrations(conn)


def _step_object_store_backfill_dry_run(company_uid: str | None, limit: int) -> dict[str, Any]:
    args = argparse.Namespace(source="ib_disclosure", document_type=None, limit=limit, dry_run=True)
    return backfill_mod.run(args)


def _step_parser_dry_run(company_uid: str | None, limit: int) -> dict[str, Any]:
    args = argparse.Namespace(
        limit=limit,
        source="ib_disclosure",
        company=None,  # company_uid isn't a policy_documents column -- see fetch_documents(); left unfiltered here
        document_extension=None,
        max_pages=200,
        max_bytes=20_000_000,
        chunk_size=1800,
        chunk_overlap=180,
        enable_windows_com=False,
        dry_run=True,
    )
    documents = parse_document_snapshots.fetch_documents(args.limit, args.source, args.company, args.document_extension)
    results = [parse_document_snapshots.parse_one(document, args) for document in documents]
    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    return {"candidates": len(documents), "summary": summary}


def run(args: argparse.Namespace) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    ok = True

    with get_inventory_connection() as conn:
        steps["migration_check"] = _step_migration_check(conn)
        ok = ok and steps["migration_check"]["ok"]

    steps["object_store_backfill_dry_run"] = _step_object_store_backfill_dry_run(args.company_uid, args.limit)
    ok = ok and not steps["object_store_backfill_dry_run"].get("errors")

    steps["parser_dry_run"] = _step_parser_dry_run(args.company_uid, args.limit)

    steps["readiness_report"] = build_readiness_report()

    deployment_readiness = check_deployment_readiness.build_report()
    steps["deployment_readiness"] = deployment_readiness
    ok = ok and not deployment_readiness["blockers"]

    return {
        "ok": ok,
        "company_uid": args.company_uid,
        "limit": args.limit,
        "steps": steps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--company-uid",
        help="Restrict the parser/backfill dry-run steps' framing to this IB company_uid "
        "(informational in this summary; the underlying dry-run calls scope by --source, "
        "see _step_parser_dry_run's docstring note -- company-level filtering in "
        "policy_documents needs a join this smoke test doesn't add scope for).",
    )
    parser.add_argument("--limit", type=int, default=20, help="Bounded sample size for the dry-run steps -- never the full backlog.")
    args = parser.parse_args()

    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if summary["ok"] else 1)


if __name__ == "__main__":
    main()
