"""Phase A: low-speed, evidence-first recovery for IB (ins-info.ib.gov.tw)
document download failures.

This is deliberately NOT "retry everything faster" -- see
scripts/sources/ib_disclosure/failure_classifier.py and
scripts/analyze_ib_download_failures.py, which this script builds on. Of
the 199 IB document failures seen for 臺灣產物 so far: ~44 are
source_not_found (the file genuinely isn't on IB's server -- retrying
changes nothing), ~7 are waf_blocked (IB's edge rejected the request --
retrying *faster* makes it worse), and the rest are unclassified_legacy
(pre-dated evidence capture, so the only way to learn what they are is one
careful low-speed look each, not a bulk re-crawl).

What this does, per run:
  1. Pick candidates from currently BROKEN_LINK/NOT_LISTED document_registry
     rows (source='ib_disclosure'), grouped by their classification (see
     failure_classifier.classify) -- at most `--max-per-category` from each
     category, optionally filtered to one `--company-uid` and/or
     `--document-type`.
  2. source_not_found is excluded by default (the task's own guidance:
     "官方文件不存在/下架 -> 標記 SOURCE_BROKEN，不用硬救") -- pass
     `--include-source-not-found` to override for a specific spot-check.
  3. `--dry-run` prints exactly which rows would be retested (and why) and
     makes zero network calls -- use it to sanity-check a batch's scope
     before spending any requests.
  4. Otherwise, replays each candidate's LinkButton postback exactly once,
     always starting with a fresh GET of the detail page for current
     __VIEWSTATE/__EVENTVALIDATION (query_client.IbQueryClient.post_event
     already does this -- never reuses stale hidden fields from an earlier
     attempt or a different row).
  5. A successful download updates document_registry to AVAILABLE and
     writes the document_snapshots row (same as
     scripts/download_ib_documents.py) -- deduped by checksum, so
     recovering the same content twice from two different rows/runs never
     writes a duplicate file.
  6. A repeat failure updates the row's evidence + classification (so the
     next run's "unclassified_legacy" bucket shrinks even when the outcome
     is still broken).
  7. If `--cooldown-on-waf` waf_blocked outcomes are hit IN THIS RUN, the
     run stops immediately -- remaining candidates are left untouched for a
     later, separately-scheduled run after a real cooldown period (this
     script does not sleep-and-retry internally; that's a human/scheduler
     decision, not something to automate blindly).

Usage:
    python scripts/recover_ib_download_failures.py --dry-run --max-per-category 3
    python scripts/recover_ib_download_failures.py --max-per-category 3 --delay-seconds 3 --cooldown-on-waf 2
    python scripts/recover_ib_download_failures.py --company-uid 03557115 --document-type RATE_TABLE --max-per-category 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
IB_DIR = ROOT / "scripts" / "sources" / "ib_disclosure"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(IB_DIR) not in sys.path:
    sys.path.insert(0, str(IB_DIR))

from inventory_db import get_inventory_connection  # noqa: E402
import inventory_repository as repo  # noqa: E402
from failure_classifier import classify  # noqa: E402
from download_ib_documents import _parse_placeholder_url  # noqa: E402
from analyze_ib_download_failures import _fetch_failed_rows, _retest_one  # noqa: E402

# See module docstring point 2 -- retrying a confirmed-missing source file
# wastes a request on something no amount of retrying fixes. Every other
# category (including waf_blocked -- the block may have lifted, and
# unclassified_legacy, which has no evidence yet at all) is a legitimate
# recovery candidate by default.
_EXCLUDED_BY_DEFAULT = {"source_not_found", "waf_false_positive"}


def _classify_row(row: dict[str, Any]) -> str:
    evidence = row["metadata"].get("download_error")
    if not evidence:
        return "unclassified_legacy"
    return classify(evidence)["category"]


def select_candidates(
    rows: list[dict[str, Any]],
    max_per_category: int,
    company_uid: str | None,
    document_type: str | None,
    include_source_not_found: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Group filtered rows by category, capped at `max_per_category` each.
    Iterates in document_registry id order so results are deterministic
    across dry-run and live runs (same candidates picked both times).
    """
    excluded = set() if include_source_not_found else _EXCLUDED_BY_DEFAULT
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in sorted(rows, key=lambda r: r["id"]):
        parsed = _parse_placeholder_url(row["url"])
        if parsed is None:
            continue  # not a replayable urn:ib-linkbutton: row -- nothing to retest
        if company_uid and parsed["company_uid"] != company_uid:
            continue
        if document_type and row["document_type"] != document_type:
            continue

        category = _classify_row(row)
        if category in excluded:
            continue
        if len(by_category[category]) >= max_per_category:
            continue
        by_category[category].append(row)

    return dict(by_category)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    with get_inventory_connection() as conn:
        rows = _fetch_failed_rows(conn)
        selected = select_candidates(
            rows, args.max_per_category, args.company_uid, args.document_type, args.include_source_not_found
        )
        candidates = [row for rows_in_category in selected.values() for row in rows_in_category]

        stats: dict[str, Any] = {
            "candidate_pool": len(rows),
            "selected": len(candidates),
            "selected_by_category": {category: len(rows_in_category) for category, rows_in_category in selected.items()},
            "dry_run": args.dry_run,
        }

        if args.dry_run:
            stats["would_retest"] = [
                {
                    "document_registry_id": row["id"],
                    "category": _classify_row(row),
                    "company_name": row["company_name"],
                    "product_code": row["product_code"],
                    "document_type": row["document_type"],
                    "title": row["title"],
                }
                for row in candidates
            ]
            return stats

        if not candidates:
            stats["attempted"] = 0
            stats["recovered"] = 0
            stats["still_broken"] = 0
            stats["waf_hits"] = 0
            stats["stopped_early"] = False
            stats["items"] = []
            return stats

        from query_client import IbQueryClient

        outcome_counts: Counter = Counter()
        waf_hits = 0
        stopped_early = False
        stop_reason = ""
        items: list[dict[str, Any]] = []

        async with IbQueryClient(min_interval_seconds=args.delay_seconds, verify=not args.insecure) as client:
            for row in candidates:
                try:
                    outcome = await _retest_one(client, row)
                except httpx.HTTPStatusError as exc:
                    code = exc.response.status_code
                    items.append({"document_registry_id": row["id"], "outcome": "http_error", "status_code": code})
                    outcome_counts["http_error"] += 1
                    if code in (403, 429):
                        stopped_early = True
                        stop_reason = f"HTTP {code} -- stopping this run, let a real cooldown pass"
                        break
                    continue
                except httpx.TransportError as exc:
                    # Timeout/connection error: nothing learned about the
                    # document, so leave its row untouched and move on.
                    items.append({"document_registry_id": row["id"], "outcome": "transport_error", "error": type(exc).__name__})
                    outcome_counts["transport_error"] += 1
                    if outcome_counts["transport_error"] >= 3:
                        stopped_early = True
                        stop_reason = "3 transport errors in a row-ish -- stopping, IB may be throttling"
                        break
                    continue
                if outcome is None:
                    outcome_counts["skipped_unparseable_url"] += 1
                    continue

                result = outcome["result"]
                if result.status == "downloaded":
                    outcome_counts["recovered"] += 1
                    repo.upsert_document_snapshot(
                        conn,
                        row["id"],
                        {
                            "url": result.download_url,
                            "final_url": result.final_url,
                            "content_type": result.content_type,
                            "local_path": result.local_path,
                            "checksum": result.checksum,
                            "file_size": result.file_size,
                        },
                    )
                    repo.update_document_registry_status(
                        conn, row["id"], availability_status="AVAILABLE", final_url=result.download_url
                    )
                    current_metadata = row["metadata"]
                    current_metadata.pop("download_error", None)
                    conn.execute(
                        "UPDATE document_registry SET metadata = ?, updated_at = datetime('now') WHERE id = ?",
                        (json.dumps(current_metadata, ensure_ascii=False), row["id"]),
                    )
                    items.append({"document_registry_id": row["id"], "outcome": "recovered", "local_path": result.local_path})
                else:
                    outcome_counts["still_broken"] += 1
                    classification = (
                        classify(result.error_evidence)
                        if result.error_evidence
                        else {"category": "html_error_unknown", "matched_pattern": None, "reasoning": "重測後仍失敗，且無新證據"}
                    )
                    if result.error_evidence:
                        repo.record_document_download_error(
                            conn, row["id"], result.error_evidence, classification, retested=True
                        )
                    items.append(
                        {
                            "document_registry_id": row["id"],
                            "outcome": "still_broken",
                            "category_after": classification["category"],
                        }
                    )
                    if classification["category"] == "waf_blocked":
                        waf_hits += 1
                        if waf_hits >= args.cooldown_on_waf:
                            stopped_early = True
                            stop_reason = (
                                f"hit {waf_hits} waf_blocked outcomes (threshold {args.cooldown_on_waf}) -- "
                                "stopping this run, let a real cooldown pass before the next one"
                            )
                            break

        stats["attempted"] = sum(outcome_counts.values())
        stats["recovered"] = outcome_counts["recovered"]
        stats["still_broken"] = outcome_counts["still_broken"]
        stats["skipped_unparseable_url"] = outcome_counts["skipped_unparseable_url"]
        stats["waf_hits"] = waf_hits
        stats["stopped_early"] = stopped_early
        stats["stop_reason"] = stop_reason
        stats["items"] = items
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-per-category", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument(
        "--cooldown-on-waf",
        type=int,
        default=2,
        help="Stop this run immediately once this many waf_blocked outcomes are seen (default 2).",
    )
    parser.add_argument("--company-uid", help="Only retest rows for this IB company_uid.")
    parser.add_argument("--document-type", help="Only retest rows of this document_registry.document_type (e.g. RATE_TABLE).")
    parser.add_argument(
        "--include-source-not-found",
        action="store_true",
        help="Also retest rows already classified source_not_found (off by default -- see module docstring).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the selected candidates, make zero network calls.")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    args = parser.parse_args()

    summary = asyncio.run(run(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("stopped_early"):
        print(f"\nStopped early: {summary.get('stop_reason', '')}", file=sys.stderr)


if __name__ == "__main__":
    main()
