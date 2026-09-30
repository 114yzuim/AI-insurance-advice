"""Check whether this project's crawler/parser pipeline is ready to run on
Railway staging -- dependencies, LibreOffice, object storage config, DB
migrations, and a few Railway-specific risk checks (raw blobs in the DB,
.doc backlog). Read-only: makes no network calls, writes nothing.

Never prints a secret: object storage credential env vars are checked for
PRESENCE only (see _check_object_storage()) -- their values never appear in
this script's output.

Usage:
    python scripts/check_deployment_readiness.py
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

# A "large blob" heuristic for the DB-hygiene check below -- not a hard
# limit anywhere else in this project, just what this checker warns about.
_LARGE_TEXT_WARN_BYTES = 200_000


def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def check_python_dependencies() -> list[dict[str, Any]]:
    modules = {
        "bs4": "beautifulsoup4",
        "pdfplumber": "pdfplumber",
        "pypdf": "pypdf",
        "docx": "python-docx",
        "openpyxl": "openpyxl",
        "xlrd": "xlrd",
    }
    results = []
    for module_name, package_name in modules.items():
        try:
            importlib.import_module(module_name)
            results.append(_check(f"python_dependency:{package_name}", True, f"import {module_name} OK"))
        except ImportError as exc:
            results.append(_check(f"python_dependency:{package_name}", False, f"import {module_name} failed: {exc}"))
    return results


def check_libreoffice() -> dict[str, Any]:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return _check("libreoffice", True, f"found at {path}")
    return _check(
        "libreoffice", False,
        "neither soffice nor libreoffice found on PATH -- .doc parsing will be parser_unavailable "
        "(see scripts/legacy_office_parser.py; Dockerfile.worker installs this for production)",
    )


def check_object_storage() -> dict[str, Any]:
    """Presence-only checks -- see module docstring. Never reads or prints
    OBJECT_STORE_ACCESS_KEY_ID / OBJECT_STORE_SECRET_ACCESS_KEY values.
    """
    backend = os.environ.get("OBJECT_STORE_BACKEND", "file").strip().lower()
    if backend == "file":
        root = os.environ.get("OBJECT_STORE_ROOT") or str(BACKEND / "data" / "object_store")
        return _check("object_storage", True, f"backend=file, root={root}")
    if backend == "s3":
        required = ("OBJECT_STORE_BUCKET", "OBJECT_STORE_ACCESS_KEY_ID", "OBJECT_STORE_SECRET_ACCESS_KEY")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            return _check(
                "object_storage", False,
                f"backend=s3 but missing required env vars: {', '.join(missing)} (values never checked/printed, only presence)",
            )
        return _check("object_storage", True, "backend=s3, all required env vars present (values not inspected)")
    return _check("object_storage", False, f"unrecognized OBJECT_STORE_BACKEND={backend!r} (expected file|s3)")


def check_migrations(conn) -> dict[str, Any]:
    from inventory_db import MIGRATIONS_DIR

    on_disk = sorted(path.stem for path in MIGRATIONS_DIR.glob("*.sql"))
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    missing = [version for version in on_disk if version not in applied]
    if missing:
        return _check("db_migrations", False, f"not yet applied: {', '.join(missing)}")
    return _check("db_migrations", True, f"{len(applied)} migrations applied, up to date with {len(on_disk)} on disk")


def check_object_store_backfill_coverage(conn) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM document_snapshots WHERE local_path != ''").fetchone()[0]
    missing = conn.execute(
        "SELECT COUNT(*) FROM document_snapshots WHERE local_path != '' AND (object_store_uri IS NULL OR object_store_uri = '')"
    ).fetchone()[0]
    if total == 0:
        return _check("object_store_backfill_coverage", True, "no document_snapshots rows yet")
    ok = missing == 0
    detail = f"{total - missing}/{total} snapshots have an object_store_uri"
    if missing:
        detail += f" -- run scripts/backfill_document_snapshots_to_object_store.py to close the gap ({missing} remaining)"
    return _check("object_store_backfill_coverage", ok, detail)


def _table_columns_with_types(conn, table_name: str) -> list[tuple[str, str]]:
    """[(column_name, type)] for `table_name`, on either engine.

    SQLite's `PRAGMA table_info(x)` has no Postgres equivalent --
    Postgres's `information_schema.columns` is the standard, portable way
    to ask the same question there. See docs/postgres_migration_notes.md's
    5-item table.
    """
    if getattr(conn, "dialect", "sqlite") == "postgres":
        rows = conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ?",
            (table_name,),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [(row[1], row[2]) for row in rows]


def check_no_raw_blobs_in_db(conn) -> dict[str, Any]:
    """Task 4: confirm document_snapshots' schema only carries pointers
    (local_path/object_store_uri/object_store_key/checksum/file_size/
    metadata-shaped columns), never raw file bytes, and flag any existing
    parsed_text row that's grown large enough to be a real production
    concern (see this script's own docstring -- large text belongs behind
    a pointer to object storage/a vector store, not inline in Postgres).
    Read-only: reports, never deletes or moves anything (Task 4's own
    constraint).
    """
    column_types = _table_columns_with_types(conn, "document_snapshots")
    columns = {name for name, _ in column_types}
    # BLOB (SQLite) / bytea (Postgres)-typed columns would be the smoking
    # gun for "raw bytes in the DB" -- this project's schema has never had
    # one, but check the live schema rather than assuming.
    disallowed_present = {name for name, col_type in column_types if (col_type or "").upper() in ("BLOB", "BYTEA")}
    ok = not disallowed_present
    detail = "document_snapshots has no BLOB/bytea columns" if ok else f"BLOB/bytea columns found: {sorted(disallowed_present)}"

    # document_snapshots.parsed_text / .tables_json exist in the schema
    # (0002_market_universe.sql) but nothing in this codebase writes to
    # them -- every parser writes to policy_documents.parsed_text instead
    # (verified live 2026-09-14, grep across scripts/ and backend/ finds no
    # writer). Flagged here, not fixed: Task 4 says report, don't touch
    # data/schema this round.
    unused_columns_present = {"parsed_text", "tables_json"} & columns
    if unused_columns_present:
        detail += (
            f"; document_snapshots also has unused {sorted(unused_columns_present)} columns "
            f"(schema leftover from 0002_market_universe.sql, nothing writes to them -- "
            f"harmless today, but a future migration could drop them to keep the pointer-only "
            f"contract explicit in the schema, not just by convention)"
        )

    large_text_row = conn.execute(
        "SELECT COUNT(*), COALESCE(MAX(LENGTH(parsed_text)), 0), COALESCE(SUM(LENGTH(parsed_text)), 0) "
        "FROM policy_documents WHERE LENGTH(parsed_text) > ?",
        (_LARGE_TEXT_WARN_BYTES,),
    ).fetchone()
    large_count, largest, total_bytes = large_text_row
    if large_count:
        detail += (
            f"; {large_count} policy_documents.parsed_text rows exceed {_LARGE_TEXT_WARN_BYTES:,} bytes "
            f"(largest {largest:,}, total {total_bytes:,}) -- fine on SQLite locally, but on Railway "
            f"Postgres consider moving parsed_text/chunks to object storage or a vector store and keeping "
            f"only a pointer in this table, same pattern as document_snapshots.object_store_uri"
        )
    return _check("no_raw_blobs_in_db", ok, detail, )


def check_doc_backlog(conn) -> dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*) FROM policy_documents WHERE LOWER(local_path) LIKE '%.doc' AND text_status = 'downloaded_not_parsed'"
    ).fetchone()
    remaining = row[0]
    if remaining == 0:
        return _check("doc_backlog", True, "no .doc documents left at downloaded_not_parsed")
    # ok=False here is a WARNING, not a blocker (see build_report()'s
    # blockers/warnings split) -- LibreOffice availability is checked
    # separately above; a nonzero backlog just means "hasn't been run yet",
    # not "can't be run".
    return _check(
        "doc_backlog", False,
        f"{remaining} .doc documents still at downloaded_not_parsed -- run scripts/parse_document_snapshots.py "
        f"--document-extension .doc once LibreOffice is available (see the libreoffice check)",
    )


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(check_python_dependencies())
    checks.append(check_libreoffice())
    checks.append(check_object_storage())

    try:
        from inventory_db import get_inventory_connection

        with get_inventory_connection() as conn:
            checks.append(check_migrations(conn))
            checks.append(check_object_store_backfill_coverage(conn))
            checks.append(check_no_raw_blobs_in_db(conn))
            checks.append(check_doc_backlog(conn))
    except Exception as exc:  # noqa: BLE001 -- a DB-open failure is itself a blocker, not a crash
        checks.append(_check("database_reachable", False, str(exc)[:300]))

    blockers = [c["name"] for c in checks if not c["ok"] and c["name"] not in ("libreoffice", "doc_backlog")]
    warnings = [c["name"] for c in checks if not c["ok"] and c["name"] in ("libreoffice", "doc_backlog")]

    return {
        "ok": not blockers,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> None:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
