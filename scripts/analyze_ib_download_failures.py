"""Analyze IB (ins-info.ib.gov.tw) document download failures -- and
optionally re-verify a *small* sample of them -- without blindly retrying
everything.

Background: scripts/download_ib_documents.py marks a document_registry row
BROKEN_LINK when DownLoad.aspx (or the postback that's supposed to resolve
it) returns HTML instead of a file. As of this script's own docstring's
writing, that happened for ~199 of 560 IB document candidates for 臺灣產物.
This is NOT necessarily 199 CAPTCHA blocks or dead links -- it could be a
parser bug (wrong LinkButton event target), a session/cookie problem, a
genuinely removed document, or a transient server error, and those need
completely different fixes. See scripts/sources/ib_disclosure/
failure_classifier.py for the category rules this script uses.

What this script does
----------------------
1. Read every document_registry row with source='ib_disclosure' and
   availability_status='BROKEN_LINK' (or 'NOT_LISTED' with recorded
   evidence -- a postback that produced no download link at all is also a
   "failure" worth classifying, see failure_classifier's inline_text
   category).
2. Classify each from its stored metadata["download_error"] evidence
   (recorded by scripts/download_ib_documents.py at fetch time -- see
   inventory_repository.record_document_download_error). Rows from before
   that instrumentation existed (no "download_error" in metadata) are
   reported separately as "unclassified_legacy" rather than guessed at.
3. Aggregate counts: by_document_type, by_status_code, by_error_title,
   by_error_text_pattern, by_category, sample_products, suggested_action.
4. Optionally (--retest), re-verify a SMALL sample (--max-per-category,
   default 3) per category: replay the exact same LinkButton postback once
   each, save fresh evidence, and mark the row `recoverable` (if it
   downloaded successfully this time -- and actually record that success,
   same as download_ib_documents.py would) or `source_broken` (if it failed
   again, with the fresh evidence saved over the stale evidence). This is
   NOT a bulk retry: it touches at most `--max-per-category` rows per
   category, uses the same throttled IbQueryClient as the real downloader,
   and never touches TII or attempts anything CAPTCHA-gated (out of scope
   for this source entirely -- see query_client.py's module docstring).

Usage:
    python scripts/analyze_ib_download_failures.py
    python scripts/analyze_ib_download_failures.py --retest --max-per-category 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
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
from failure_classifier import classify, suggested_action  # noqa: E402
from download_ib_documents import _parse_placeholder_url  # noqa: E402

_RELEVANT_STATUSES = ("BROKEN_LINK", "NOT_LISTED")


def _fetch_failed_rows(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            dr.id, dr.document_type, dr.title, dr.url, dr.availability_status, dr.metadata,
            spr.company_name, spr.product_code, spr.product_name
        FROM document_registry dr
        LEFT JOIN source_product_records spr ON spr.id = dr.source_record_id
        WHERE dr.source = 'ib_disclosure' AND dr.availability_status IN ({})
        ORDER BY dr.id
        """.format(",".join("?" * len(_RELEVANT_STATUSES))),
        _RELEVANT_STATUSES,
    ).fetchall()

    out = []
    for row in rows:
        (doc_id, document_type, title, url, availability_status, metadata_json,
         company_name, product_code, product_name) = row
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except json.JSONDecodeError:
            metadata = {}
        out.append(
            {
                "id": doc_id,
                "document_type": document_type,
                "title": title,
                "url": url,
                "availability_status": availability_status,
                "metadata": metadata,
                "company_name": company_name or "",
                "product_code": product_code or "",
                "product_name": product_name or "",
            }
        )
    return out


def build_analysis(conn, sample_size: int = 5) -> dict[str, Any]:
    rows = _fetch_failed_rows(conn)

    by_document_type: Counter = Counter()
    by_status_code: Counter = Counter()
    by_error_title: Counter = Counter()
    by_error_text_pattern: Counter = Counter()
    by_category: Counter = Counter()
    samples_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unclassified_legacy = 0

    for row in rows:
        evidence = row["metadata"].get("download_error")
        by_document_type[row["document_type"]] += 1

        if not evidence:
            unclassified_legacy += 1
            category = "unclassified_legacy"
        else:
            # Always re-derive from the raw evidence with the CURRENT
            # classifier rules, rather than trusting whatever category was
            # cached in metadata at capture time -- failure_classifier.py's
            # patterns get refined as new evidence is seen (see its
            # 2026-09-14 "不存在" addition), and stale cached categories
            # would silently stop reflecting that. This script is the
            # single source of truth for "what category is this row in
            # right now".
            category = classify(evidence)["category"]
            if evidence.get("status_code"):
                by_status_code[evidence["status_code"]] += 1
            if evidence.get("title"):
                by_error_title[evidence["title"]] += 1
            pattern = evidence.get("matched_pattern")
            if pattern:
                by_error_text_pattern[pattern] += 1

        by_category[category] += 1
        if len(samples_by_category[category]) < sample_size:
            samples_by_category[category].append(
                {
                    "document_registry_id": row["id"],
                    "company_name": row["company_name"],
                    "product_code": row["product_code"],
                    "product_name": row["product_name"],
                    "document_type": row["document_type"],
                    "title": row["title"],
                    "availability_status": row["availability_status"],
                    "error_title": (evidence or {}).get("title", ""),
                    "error_text_sample": (evidence or {}).get("text_sample", ""),
                }
            )

    return {
        "failed_total": len(rows),
        "unclassified_legacy": unclassified_legacy,
        "by_document_type": dict(by_document_type),
        "by_status_code": {str(k): v for k, v in by_status_code.items()},
        "by_error_title": dict(by_error_title.most_common(20)),
        "by_error_text_pattern": dict(by_error_text_pattern.most_common(20)),
        "by_category": dict(by_category),
        "sample_products": {category: items for category, items in samples_by_category.items()},
        "suggested_action": {category: suggested_action(category) for category in by_category},
    }


async def _retest_one(client, row: dict[str, Any]) -> dict[str, Any] | None:
    from download_client import DEFAULT_DOCUMENT_SNAPSHOT_DIR, download_document

    parsed = _parse_placeholder_url(row["url"])
    if parsed is None:
        return None  # not one of ours (or url got rewritten) -- can't replay
    detail_url = (
        f"https://ins-info.ib.gov.tw/customer/property5-1-{parsed['function_number']}.aspx"
        f"?UID={parsed['company_uid']}&proc={parsed['product_code']}"
    )
    result = await download_document(
        client, detail_url, parsed["event_target"], snapshot_dir=DEFAULT_DOCUMENT_SNAPSHOT_DIR
    )
    return {"row": row, "result": result}


async def run_retest(
    conn, analysis: dict[str, Any], max_per_category: int, delay_seconds: float, insecure: bool = False
) -> dict[str, Any]:
    from query_client import IbQueryClient

    # "unclassified_legacy" (rows that went BROKEN_LINK before this
    # instrumentation existed, so they have no stored evidence at all) is
    # included here too, capped the same as every other category -- it's
    # the only way to ever get real evidence for those rows without a bulk
    # re-crawl, and the task explicitly asked for evidence-first
    # classification over blind mass retrying.
    to_retest: list[dict[str, Any]] = []
    for category, samples in analysis["sample_products"].items():
        to_retest.extend(samples[:max_per_category])

    retest_stats = {"attempted": 0, "recoverable": 0, "source_broken": 0, "skipped_unparseable_url": 0, "items": []}
    if not to_retest:
        return retest_stats

    async with IbQueryClient(min_interval_seconds=delay_seconds, verify=not insecure) as client:
        for sample in to_retest:
            row = next((r for r in _fetch_failed_rows(conn) if r["id"] == sample["document_registry_id"]), None)
            if row is None:
                continue
            outcome = await _retest_one(client, row)
            if outcome is None:
                retest_stats["skipped_unparseable_url"] += 1
                continue

            retest_stats["attempted"] += 1
            result = outcome["result"]
            if result.status == "downloaded":
                retest_stats["recoverable"] += 1
                row_id, created = repo.upsert_document_snapshot(
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
                # Record success as a resolved download_error so it's no
                # longer surfaced by the next build_analysis() run.
                current_metadata = row["metadata"]
                current_metadata.pop("download_error", None)
                conn.execute(
                    "UPDATE document_registry SET metadata = ?, updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(current_metadata, ensure_ascii=False), row["id"]),
                )
                retest_stats["items"].append(
                    {"document_registry_id": row["id"], "outcome": "recoverable", "local_path": result.local_path}
                )
            else:
                retest_stats["source_broken"] += 1
                classification = classify(result.error_evidence) if result.error_evidence else {
                    "category": "unknown", "matched_pattern": None, "reasoning": "重測後仍失敗，且無新證據"
                }
                if result.error_evidence:
                    repo.record_document_download_error(
                        conn, row["id"], result.error_evidence, classification, retested=True
                    )
                # keep availability_status as-is (BROKEN_LINK/NOT_LISTED) --
                # a second failure is still just the same failure, not a new
                # fact, other than the fresh evidence just recorded.
                retest_stats["items"].append(
                    {
                        "document_registry_id": row["id"],
                        "outcome": "source_broken",
                        "category_before": sample.get("error_title", ""),
                        "category_after": classification["category"],
                    }
                )

    return retest_stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-size", type=int, default=5, help="Sample products to include per category in the report.")
    parser.add_argument("--retest", action="store_true", help="Re-verify a small sample of failures live (see module docstring).")
    parser.add_argument("--max-per-category", type=int, default=3)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    args = parser.parse_args()

    with get_inventory_connection() as conn:
        analysis = build_analysis(conn, sample_size=args.sample_size)
        output: dict[str, Any] = {"analysis": analysis}
        if args.retest:
            output["retest"] = asyncio.run(
                run_retest(conn, analysis, args.max_per_category, args.delay_seconds, args.insecure)
            )
            # Re-run analysis after retest so the printed report reflects
            # rows that just got fixed / re-confirmed broken.
            output["analysis_after_retest"] = build_analysis(conn, sample_size=args.sample_size)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
