"""Generate backend/inventory_migrations_pg/*.sql from
backend/inventory_migrations/*.sql -- the SQLite migrations stay the single
source of truth (existing authoring convention, existing tooling in
backend/inventory_db.py); this mechanically derives the Postgres-dialect
equivalent so the two never hand-drift apart.

What this translates (verified sufficient for 0001-0004 -- see
docs/postgres_migration_notes.md for the full compatibility audit this was
built from):

  INTEGER PRIMARY KEY AUTOINCREMENT  -> SERIAL PRIMARY KEY (or the
      identifier before "INTEGER PRIMARY KEY AUTOINCREMENT" is dropped
      since SERIAL already implies integer)
  DEFAULT (datetime('now'))          -> DEFAULT (to_char(now() at time
      zone 'utc', 'YYYY-MM-DD HH24:MI:SS')) -- keeps the exact SQLite
      string format ("2026-09-18 10:23:45", no timezone suffix) for
      every TEXT-typed timestamp column, so nothing downstream that
      parses/sorts/compares these strings needs to change.
  CREATE INDEX idx_chunks_text ON policy_document_chunks(text)
      -> DROPPED for Postgres. Verified live 2026-09-18: a plain btree
      index over the full `text` column (chunk bodies up to ~1800 chars,
      often Traditional Chinese so 3 bytes/char in UTF-8) hits Postgres's
      hard ~2704-byte-per-index-entry btree limit and makes INSERTs into
      policy_document_chunks fail outright once a chunk is long enough --
      not a soft warning, a hard `ProgramLimitExceeded` error. SQLite has
      no such limit, which is why this was invisible there. Confirmed via
      grep across scripts/*.py and backend/*.py that nothing anywhere
      queries `policy_document_chunks.text` by equality/prefix (the index
      is unused dead weight even on SQLite) -- safe to drop rather than
      needing a workaround like a functional index on a hash of the text.

What this does NOT translate (none of these patterns exist in 0001-0004,
verified by scripts/audit_sqlite_postgres_compat.py -- this script would
need extending, not just re-running, if a future migration adds one):
  - json_each() / other SQLite JSON1 functions (Postgres: jsonb_array_
    elements_text() -- different enough in shape that call-site SQL, not
    DDL, needs hand rewriting; see scripts/inventory_repository.py callers)
  - GROUP_CONCAT (Postgres: STRING_AGG -- also a call-site rewrite)
  - TRIGGER definitions
  - Any column whose default isn't `datetime('now')`

Idempotent: re-running overwrites backend/inventory_migrations_pg/ from
scratch every time -- never hand-edit files in that directory.

Usage:
    python scripts/translate_migrations_to_postgres.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "backend" / "inventory_migrations"
TARGET_DIR = ROOT / "backend" / "inventory_migrations_pg"

_AUTOINCREMENT_RE = re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.IGNORECASE)
_DATETIME_NOW_DEFAULT_RE = re.compile(r"datetime\(\s*'now'\s*\)")
_PG_NOW_TEXT = "to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')"
_UNSUPPORTED_INDEX_RE = re.compile(
    r"CREATE INDEX IF NOT EXISTS idx_chunks_text ON policy_document_chunks\(text\);\n?"
)


PG_ONLY_DIR = SOURCE_DIR.parent / "inventory_migrations_pg_only"


def translate_sql(sql: str) -> str:
    sql = _AUTOINCREMENT_RE.sub("SERIAL PRIMARY KEY", sql)
    sql = _DATETIME_NOW_DEFAULT_RE.sub(_PG_NOW_TEXT, sql)
    sql = _UNSUPPORTED_INDEX_RE.sub(
        "-- idx_chunks_text DROPPED for Postgres -- see this script's module docstring\n", sql
    )
    return sql


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for existing in TARGET_DIR.glob("*.sql"):
        existing.unlink()

    translated = []
    for source_path in sorted(SOURCE_DIR.glob("*.sql")):
        pg_sql = translate_sql(source_path.read_text(encoding="utf-8"))
        target_path = TARGET_DIR / source_path.name
        header = (
            f"-- AUTO-GENERATED from backend/inventory_migrations/{source_path.name} by\n"
            f"-- scripts/translate_migrations_to_postgres.py -- do not hand-edit, re-run that\n"
            f"-- script instead after changing the source SQLite migration.\n\n"
        )
        target_path.write_text(header + pg_sql, encoding="utf-8")
        translated.append(source_path.name)

    # Postgres-only migrations (pgvector, pg_trgm, ...) have no SQLite
    # source to translate from; they live in their own directory and are
    # copied verbatim, so wiping TARGET_DIR above never loses them.
    copied = []
    for pg_only_path in sorted(PG_ONLY_DIR.glob("*.sql")):
        (TARGET_DIR / pg_only_path.name).write_text(pg_only_path.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(pg_only_path.name)

    print(f"Translated {len(translated)} migration(s) into {TARGET_DIR}: {', '.join(translated)}")
    if copied:
        print(f"Copied {len(copied)} Postgres-only migration(s): {', '.join(copied)}")


if __name__ == "__main__":
    main()
