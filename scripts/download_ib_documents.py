"""Phase 2.10: download the actual files behind IB's LinkButton documents.

scripts/resolve_ib_product_details.py (Phase 2.9) already wrote a
document_registry row for every LinkButton-only document it found, keyed on
a synthesized `urn:ib-linkbutton:<company_uid>:<product_code>:
<function_number>:<event_target>` placeholder (real evidence, no fake
download URL -- see that script's module docstring). This script is the
follow-up: parse that placeholder back into its parts, replay the LinkButton
postback (scripts/sources/ib_disclosure/download_client.py -- verified live,
see its module docstring), and if a real file comes back, record it properly:

  - document_snapshots gets the actual bytes' checksum/content_type/
    local_path/file_size, AND the resolved `DownLoad.aspx?file=...` URL as
    that snapshot's own `url`/`final_url` (content-addressed on disk, so a
    re-run that downloads byte-identical content doesn't write a duplicate
    file or row -- see download_client.save_document_snapshot and
    inventory_repository.upsert_document_snapshot).
  - document_registry.url is deliberately LEFT AS the `urn:ib-linkbutton:...`
    placeholder, not overwritten with the resolved DownLoad.aspx URL --
    verified live that this token is NOT stable: two separate postback
    replays of the exact same LinkButton produced two different `file=`
    tokens. It's a one-time-use download ticket, not a durable document
    identifier, so it would go stale immediately if treated as "the" URL
    for this document; the placeholder remains the only reliable, stable
    key for "this specific document on this specific product". Only
    availability_status changes on document_registry: AVAILABLE on a
    successful download, BROKEN_LINK on an HTML/error response,
    NOT_LISTED when the postback produced no download link at all. A
    failed attempt never erases anything already known.

Only document_registry rows whose url starts with the `urn:ib-linkbutton:`
scheme are candidates -- a row that already has a real URL (or is some
other source's document) is left untouched.

Usage:
    python scripts/download_ib_documents.py --limit 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

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
from query_client import IbQueryClient  # noqa: E402
from download_client import DEFAULT_DOCUMENT_SNAPSHOT_DIR, download_document  # noqa: E402
from failure_classifier import classify  # noqa: E402
from object_storage import document_key, object_store_from_env  # noqa: E402

_URN_PREFIX = "urn:ib-linkbutton:"


def _parse_placeholder_url(url: str) -> dict[str, str] | None:
    """"urn:ib-linkbutton:<uid>:<product_code>:<function_number>:<event_target>"
    -> its parts, or None if `url` isn't one of these placeholders.
    """
    if not url.startswith(_URN_PREFIX):
        return None
    rest = url[len(_URN_PREFIX):]
    parts = rest.split(":", 3)
    if len(parts) != 4:
        return None
    company_uid, product_code, function_number, event_target = parts
    return {
        "company_uid": company_uid,
        "product_code": product_code,
        "function_number": function_number,
        "event_target": event_target,
    }


def _fetch_candidates(conn, limit: int) -> tuple[int, list[dict[str, Any]]]:
    total = conn.execute(
        "SELECT COUNT(*) FROM document_registry WHERE url LIKE ?", (f"{_URN_PREFIX}%",)
    ).fetchone()[0]

    rows = conn.execute(
        "SELECT id, url FROM document_registry WHERE url LIKE ? ORDER BY id LIMIT ?",
        (f"{_URN_PREFIX}%", limit),
    ).fetchall()

    candidates = []
    for row_id, url in rows:
        parsed = _parse_placeholder_url(url)
        if parsed is None:
            continue
        candidates.append({"id": row_id, "placeholder_url": url, **parsed})
    return total, candidates


async def run(args: argparse.Namespace) -> dict[str, Any]:
    stats = {
        "candidates": 0,
        "downloaded": 0,
        "no_download_link": 0,
        "html_error": 0,
        "failed": 0,
        "skipped_existing_checksum": 0,
        "rate_limited": False,
        "errors": [],
    }

    with get_inventory_connection() as conn:
        repo.ensure_default_sources(conn)
        total, candidates = _fetch_candidates(conn, args.limit)
        stats["candidates"] = total
        if not candidates:
            return stats

        crawl_run_id = repo.create_crawl_run(
            conn, "ib_disclosure", "refresh", metadata={"script": "download_ib_documents.py", "limit": args.limit}
        )

        async with IbQueryClient(
            snapshot_dir=args.snapshot_dir,
            min_interval_seconds=args.delay_seconds,
            timeout=args.timeout,
            verify=not args.insecure,
        ) as client:
            for candidate in candidates:
                detail_url = (
                    f"https://ins-info.ib.gov.tw/customer/property5-1-{candidate['function_number']}.aspx"
                    f"?UID={candidate['company_uid']}&proc={candidate['product_code']}"
                )
                try:
                    result = await download_document(
                        client, detail_url, candidate["event_target"], snapshot_dir=args.document_snapshot_dir
                    )
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in (403, 429):
                        stats["rate_limited"] = True
                        stats["errors"].append({"id": candidate["id"], "error": f"HTTP {status} -- stopping"})
                        break
                    stats["failed"] += 1
                    stats["errors"].append({"id": candidate["id"], "error": f"HTTP {status}"})
                    continue
                except httpx.TransportError as exc:
                    stats["failed"] += 1
                    stats["errors"].append({"id": candidate["id"], "error": str(exc)[:240]})
                    continue

                stats[result.status] = stats.get(result.status, 0) + 1

                if result.status == "downloaded":
                    snapshot = {
                        "url": result.download_url,
                        "final_url": result.final_url,
                        "content_type": result.content_type,
                        "local_path": result.local_path,
                        "checksum": result.checksum,
                        "file_size": result.file_size,
                    }
                    # Also write the bytes to object storage (Task 5, in
                    # addition to -- not instead of -- the existing local
                    # snapshot file at result.local_path; that file is never
                    # deleted here). Best-effort: an object-store failure
                    # (e.g. a misconfigured S3 backend) must not lose an
                    # otherwise-successful download, so it's recorded as a
                    # warning, not turned into a "failed" outcome.
                    object_store = getattr(args, "object_store", None)
                    if object_store is not None:
                        try:
                            local_file = ROOT / result.local_path
                            ext = local_file.suffix
                            key = document_key("ib_disclosure", result.checksum, ext)
                            ref = object_store.put_bytes(
                                key, local_file.read_bytes(), content_type=result.content_type
                            )
                            snapshot["object_store_uri"] = ref.uri
                            snapshot["object_store_key"] = ref.key
                        except Exception as exc:  # noqa: BLE001 -- object storage is additive, never blocking
                            stats["errors"].append(
                                {"id": candidate["id"], "error": f"object_storage write failed: {exc}"[:240]}
                            )

                    row_id, created = repo.upsert_document_snapshot(conn, candidate["id"], snapshot)
                    if not created:
                        stats["skipped_existing_checksum"] += 1
                    repo.update_document_registry_status(
                        conn, candidate["id"], availability_status="AVAILABLE", final_url=result.download_url
                    )
                elif result.status == "no_download_link":
                    repo.update_document_registry_status(conn, candidate["id"], availability_status="NOT_LISTED")
                    if result.error_evidence:
                        classification = classify(result.error_evidence)
                        repo.record_document_download_error(conn, candidate["id"], result.error_evidence, classification)
                elif result.status == "html_error":
                    repo.update_document_registry_status(conn, candidate["id"], availability_status="BROKEN_LINK")
                    classification = classify(result.error_evidence)
                    repo.record_document_download_error(conn, candidate["id"], result.error_evidence, classification)
                    stats["errors"].append(
                        {"id": candidate["id"], "error": result.error or "html_error", "category": classification["category"]}
                    )

        repo.finish_crawl_run(
            conn,
            crawl_run_id,
            status="failed" if stats["errors"] and not stats["rate_limited"] else "succeeded",
            records_seen=len(candidates),
            records_changed=stats["downloaded"],
            error="; ".join(str(e) for e in stats["errors"][:5]),
        )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--snapshot-dir", type=Path, default=BACKEND / "data" / "ib_disclosure_snapshots")
    parser.add_argument("--document-snapshot-dir", type=Path, default=DEFAULT_DOCUMENT_SNAPSHOT_DIR)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    parser.add_argument(
        "--no-object-store",
        action="store_true",
        help="Skip the object_storage.py write -- only the existing local snapshot file is kept "
        "(useful for a quick manual test run without touching backend/data/object_store).",
    )
    args = parser.parse_args()
    args.object_store = None if args.no_object_store else object_store_from_env()

    summary = asyncio.run(run(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["rate_limited"]:
        print("\nStopped early: HTTP 403/429 (rate limited).", file=sys.stderr)


if __name__ == "__main__":
    main()
