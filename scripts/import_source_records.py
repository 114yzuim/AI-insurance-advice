"""Import a JSONL file of SourceProductRecord-shaped rows into the Phase-2
market-universe tables (source_product_records + document_registry).

Input format: one JSON object per line, matching what
scripts/ingest_tii_product.py (or a future IB importer) writes -- notably a
"source" field ("tii", "ib_disclosure", ...), "source_product_id", and a
"documents" list of {label, url, open_id, document_type}. Any record missing
"source_product_id" is skipped and counted as an error rather than crashing
the whole run.

This only stages data into source_product_records / document_registry. It
does not touch product_families / product_versions / reconciliation_findings
(that's Phase 3's matching step) or the existing insurance_products /
policy_documents / policy_document_chunks tables.

Usage:
    python scripts/import_source_records.py \\
        --input backend/data/tii_source_records.jsonl
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

DEFAULT_INPUT = BACKEND / "data" / "tii_source_records.jsonl"


def _to_source_record(payload: dict[str, Any], crawl_run_id: int) -> dict[str, Any]:
    return {
        "source_product_id": payload["source_product_id"],
        "source_product_url": payload.get("detail_url") or payload.get("source_product_url") or "",
        "company_name": payload.get("company_name") or "",
        "product_code": payload.get("product_code") or "",
        "product_name": payload.get("product_name") or "",
        "insurance_category": payload.get("insurance_category") or "",
        "insurance_type": payload.get("insurance_type") or "",
        "sale_start_date": payload.get("sale_start_date") or "",
        "sale_end_date": payload.get("sale_end_date") or "",
        "approval_date": payload.get("approval_date") or "",
        "approval_number": payload.get("approval_number") or "",
        "filing_number": payload.get("filing_number") or "",
        "review_method": payload.get("review_method") or "",
        "raw_payload": payload,
        "crawl_run_id": crawl_run_id,
    }


def _to_document_record(doc: dict[str, Any], source_code: str) -> dict[str, Any]:
    known = {"url", "document_type", "label", "open_id"}
    return {
        "url": doc["url"],
        "document_type": doc.get("document_type") or "OTHER",
        "title": doc.get("label") or "",
        "source": source_code,
        "source_document_id": doc.get("open_id") or "",
        "metadata": {k: v for k, v in doc.items() if k not in known},
    }


def run(input_path: Path, run_type: str, default_source: str | None) -> dict[str, Any]:
    lines = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    crawl_runs: dict[str, int] = {}
    seen: dict[str, int] = {}
    changed: dict[str, int] = {}
    errors: dict[str, list[str]] = {}
    documents_seen = 0

    with get_inventory_connection() as conn:
        repo.ensure_default_sources(conn)

        for line_no, line in enumerate(lines, start=1):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.setdefault("_parse", []).append(f"line {line_no}: invalid JSON ({exc})")
                continue

            source_code = payload.get("source") or default_source
            if not source_code:
                errors.setdefault("_parse", []).append(
                    f"line {line_no}: no \"source\" field and no --default-source given"
                )
                continue
            if "source_product_id" not in payload:
                errors.setdefault(source_code, []).append(f"line {line_no}: missing source_product_id")
                continue

            if source_code not in crawl_runs:
                crawl_runs[source_code] = repo.create_crawl_run(
                    conn, source_code, run_type, metadata={"input_file": str(input_path)}
                )
                seen[source_code] = 0
                changed[source_code] = 0

            try:
                record = _to_source_record(payload, crawl_runs[source_code])
                record_id, record_changed = repo.upsert_source_product_record(conn, source_code, record)
            except Exception as exc:  # noqa: BLE001 -- one bad line shouldn't abort the whole import
                errors.setdefault(source_code, []).append(f"line {line_no}: {exc}")
                continue

            seen[source_code] += 1
            if record_changed:
                changed[source_code] += 1

            for doc in payload.get("documents", []):
                try:
                    doc_record = _to_document_record(doc, source_code)
                    repo.upsert_document_registry(conn, record_id, doc_record)
                    documents_seen += 1
                except Exception as exc:  # noqa: BLE001
                    errors.setdefault(source_code, []).append(
                        f"line {line_no}: document {doc.get('url', '?')}: {exc}"
                    )

        for source_code, crawl_run_id in crawl_runs.items():
            source_errors = errors.get(source_code, [])
            repo.finish_crawl_run(
                conn,
                crawl_run_id,
                status="failed" if source_errors else "succeeded",
                records_seen=seen.get(source_code, 0),
                records_changed=changed.get(source_code, 0),
                error="; ".join(source_errors[:5]),
            )

    return {
        "input": str(input_path),
        "lines_read": len(lines),
        "documents_seen": documents_seen,
        "by_source": {
            code: {"records_seen": seen.get(code, 0), "records_changed": changed.get(code, 0)}
            for code in crawl_runs
        },
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-type", default="import")
    parser.add_argument(
        "--default-source",
        help="Source code to use for lines missing a \"source\" field (normally unnecessary)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"input file not found: {args.input}")

    summary = run(args.input, args.run_type, args.default_source)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
