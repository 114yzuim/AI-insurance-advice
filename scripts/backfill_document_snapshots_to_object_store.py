"""Backfill existing document_snapshots into object storage -- purely local,
never touches IB/TII.

Every snapshot already on disk (local_path, from a download that already
happened) but missing object_store_uri/object_store_key (the common case:
either downloaded before scripts/object_storage.py existed, or downloaded
by a run with --no-object-store, or hit the checksum-dedup path in
scripts/inventory_repository.upsert_document_snapshot before that
function's own backfill-on-touch was added) gets its bytes read off disk
and written into the configured object store, then the DB row updated with
the resulting ObjectRef.

This is the safe way to catch up object_store_documents without re-hitting
IB's WAF/rate limits -- see scripts/download_ib_documents.py's module
docstring for why re-downloading is expensive and risky, and
scripts/recover_ib_download_failures.py for the one place in this project
that IS allowed to make new IB requests (bounded, sampled, never this).

Usage:
    python scripts/backfill_document_snapshots_to_object_store.py --source ib_disclosure
    python scripts/backfill_document_snapshots_to_object_store.py --dry-run --limit 20
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
from object_storage import document_key, object_store_from_env  # noqa: E402


def fetch_candidates(
    conn, source: str | None, document_type: str | None, limit: int
) -> list[dict[str, Any]]:
    where = [
        "ds.local_path != ''",
        "ds.local_path IS NOT NULL",
        "(ds.object_store_uri IS NULL OR ds.object_store_uri = '')",
    ]
    params: list[Any] = []
    if source:
        where.append("dr.source = ?")
        params.append(source)
    if document_type:
        where.append("dr.document_type = ?")
        params.append(document_type)
    sql = f"""
        SELECT ds.id, ds.local_path, ds.checksum, ds.content_type, dr.source, dr.document_type
        FROM document_snapshots ds
        JOIN document_registry dr ON dr.id = ds.document_registry_id
        WHERE {' AND '.join(where)}
        ORDER BY ds.id
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "snapshot_id": row[0],
            "local_path": row[1],
            "checksum": row[2],
            "content_type": row[3],
            "source": row[4],
            "document_type": row[5],
        }
        for row in rows
    ]


def _count_already_backfilled(conn, source: str | None, document_type: str | None) -> int:
    where = ["ds.local_path != ''", "ds.object_store_uri IS NOT NULL", "ds.object_store_uri != ''"]
    params: list[Any] = []
    if source:
        where.append("dr.source = ?")
        params.append(source)
    if document_type:
        where.append("dr.document_type = ?")
        params.append(document_type)
    sql = f"""
        SELECT COUNT(*) FROM document_snapshots ds
        JOIN document_registry dr ON dr.id = ds.document_registry_id
        WHERE {' AND '.join(where)}
    """
    return conn.execute(sql, params).fetchone()[0]


def run(args: argparse.Namespace) -> dict[str, Any]:
    stats = {
        "candidates": 0,
        "backfilled": 0,
        "skipped_existing": 0,
        "missing_local_file": 0,
        "failed": 0,
        "dry_run": args.dry_run,
        "errors": [],
    }

    object_store = None if args.dry_run else object_store_from_env()

    with get_inventory_connection() as conn:
        stats["skipped_existing"] = _count_already_backfilled(conn, args.source, args.document_type)
        candidates = fetch_candidates(conn, args.source, args.document_type, args.limit)
        stats["candidates"] = len(candidates)

        for candidate in candidates:
            local_path = ROOT / candidate["local_path"]
            if not local_path.exists():
                stats["missing_local_file"] += 1
                stats["errors"].append({"snapshot_id": candidate["snapshot_id"], "error": f"local file not found: {candidate['local_path']}"})
                continue

            checksum = candidate["checksum"] or ""
            if not checksum:
                # No checksum recorded -- document_key() needs one to build
                # a stable key, and a snapshot without one predates the
                # content-addressed convention entirely. Skip rather than
                # invent a key that wouldn't dedupe against a real download
                # of the same content later.
                stats["failed"] += 1
                stats["errors"].append({"snapshot_id": candidate["snapshot_id"], "error": "no checksum recorded"})
                continue

            if args.dry_run:
                stats["backfilled"] += 1  # "would backfill" -- see items list below
                continue

            ext = local_path.suffix
            key = document_key(candidate["source"] or "unknown", checksum, ext)
            try:
                data = local_path.read_bytes()
                ref = object_store.put_bytes(key, data, content_type=candidate["content_type"] or None)
            except Exception as exc:  # noqa: BLE001 -- one bad file shouldn't abort the whole backfill
                stats["failed"] += 1
                stats["errors"].append({"snapshot_id": candidate["snapshot_id"], "error": str(exc)[:240]})
                continue

            conn.execute(
                "UPDATE document_snapshots SET object_store_uri = ?, object_store_key = ? WHERE id = ?",
                (ref.uri, ref.key, candidate["snapshot_id"]),
            )
            stats["backfilled"] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="Only backfill document_registry.source = this (e.g. ib_disclosure).")
    parser.add_argument("--document-type", help="Only backfill this document_registry.document_type (e.g. RATE_TABLE).")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="Report what would be backfilled, write nothing.")
    args = parser.parse_args()

    summary = run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"] and not summary["dry_run"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
