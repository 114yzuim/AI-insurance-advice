"""A psycopg2 connection wrapper that speaks the same `?`-placeholder,
`sqlite3.Row`-like-row dialect as sqlite3 -- so the ~25 scripts and
~1000 `conn.execute(sql, params)` call sites written against
`backend/inventory_db.py`'s sqlite3 connections work UNCHANGED against
Postgres, without a file-by-file rewrite.

This is deliberately a thin, mechanical shim, not an ORM: it only
translates two things --
  1. `?` positional placeholders -> psycopg2's native `%s` (outside string
     literals -- see _translate_placeholders()'s docstring for the one
     case this does NOT handle, and why that case doesn't occur in this
     project's SQL).
  2. Row objects that support BOTH `row[0]` (positional, used everywhere
     via tuple-unpacking like `for a, b in rows`) AND `row["col"]` /
     `dict(row)` (named, used by inventory_db.row_to_dict()) -- exactly
     sqlite3.Row's own dual behavior, reimplemented here since psycopg2
     doesn't have an equivalent by default.

What this does NOT paper over -- these need explicit call-site changes,
NOT a shim, because the underlying operation genuinely differs (see
docs/postgres_migration_notes.md for the full audit this is one piece of):
  - `cursor.lastrowid` (SQLite) has no Postgres equivalent -- every INSERT
    that relies on it needs `RETURNING id` added and the id read from
    `cursor.fetchone()[0]` instead. ~7 call sites, see the audit doc.
  - `json_each(...)` (SQLite JSON1) -> `jsonb_array_elements_text(col::jsonb)`
    (Postgres) -- 2 call sites (scripts/import_inventory.py,
    scripts/report_requested_company_coverage.py).
  - `GROUP_CONCAT(...)` -> `STRING_AGG(...)` -- 2 call sites
    (scripts/report_inventory_quality.py).
  - `INSERT OR REPLACE` -> `INSERT ... ON CONFLICT (...) DO UPDATE SET ...`
    -- 1 call site (backend/inventory_db.py's seed loader).
  - `PRAGMA table_info(x)` -> a query against `information_schema.columns`
    -- 2 call sites (scripts/check_deployment_readiness.py).
  - `PRAGMA foreign_keys = ON` -- simply not needed; Postgres always
    enforces foreign keys. This wrapper's `execute()` silently no-ops any
    PRAGMA statement passed to it so callers don't need an `if` around it.

Usage (mirrors backend/inventory_db.get_inventory_connection()'s shape):
    with get_pg_connection(dsn) as conn:
        conn.execute("SELECT id, name FROM inventory_sources WHERE code = ?", (code,))
        row = conn.fetchone()
        row[0], row["name"]  # both work
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Sequence

import psycopg2
import psycopg2.extensions

# SQLite's datetime('now') appears not just in migration DDL defaults
# (handled separately by scripts/translate_migrations_to_postgres.py) but
# inline in ~39 runtime UPDATE/INSERT statements across this project's
# scripts (e.g. `SET updated_at = datetime('now')`) -- translated here too,
# to the exact same to_char(...) expression the migration translator uses,
# so a TEXT column's value has the identical "YYYY-MM-DD HH:MM:SS" shape
# regardless of which of the two translators produced the SQL that wrote it.
_DATETIME_NOW_RE = re.compile(r"datetime\(\s*'now'\s*\)")
_PG_NOW_TEXT_EXPR = "to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')"

# Matches a `?` that is NOT inside a single-quoted SQL string literal.
# This project's SQL never puts a literal `?` character inside a string
# value (verified live 2026-09-18 -- grep across scripts/*.py's SQL text
# for `'...?...'` finds none), so a corpus-verified simplification is used
# instead of a full SQL tokenizer: split on single-quoted spans first, only
# translate `?` in the spans OUTSIDE quotes.
_QUOTED_SPAN_RE = re.compile(r"'(?:[^']|'')*'")


def _translate_placeholders(sql: str) -> str:
    """`?` -> `%s`, skipping anything inside '...' string literals (so a
    literal '?' character INSIDE a quoted string, if one ever appears,
    is left alone -- doesn't happen in this project's SQL today, but this
    is cheap insurance against a future migration silently corrupting a
    string literal).
    """
    parts = []
    last_end = 0
    for match in _QUOTED_SPAN_RE.finditer(sql):
        parts.append(sql[last_end : match.start()].replace("?", "%s"))
        parts.append(match.group(0))
        last_end = match.end()
    parts.append(sql[last_end:].replace("?", "%s"))
    return "".join(parts)


def _translate_sql(sql: str, has_params: bool) -> str:
    """`has_params` controls a psycopg2-specific gotcha, not a cosmetic
    choice: psycopg2's parameter substitution (triggered whenever `vars`
    is non-None on cursor.execute()) does Python-style `%`-template
    scanning over the ENTIRE query text -- so a perfectly ordinary LIKE
    pattern like `'%guide%'` is not inert text to it: `%g` is itself a
    valid conversion specifier (like `%s`/%d`), and gets silently consumed
    as if it were a real placeholder needing an argument, which is exactly
    what caused a real, verified-live `IndexError: tuple index out of
    range` on scripts/report_inventory_quality.py's `'%guide%'`/`'%導讀%'`
    patterns once real params were involved. The fix is escaping every
    LITERAL `%` in the source SQL as `%%` -- but only when params are
    actually going to be substituted (`has_params=True`); when a query has
    no params at all this method's caller passes `vars=None` to psycopg2,
    which skips %-scanning entirely, so escaping here would be wrong (it
    would send literal `%%guide%%` to Postgres and silently break the LIKE
    pattern instead of matching anything).
    """
    sql = _DATETIME_NOW_RE.sub(_PG_NOW_TEXT_EXPR, sql)
    if has_params:
        sql = sql.replace("%", "%%")
    return _translate_placeholders(sql)


def _strip_nul_bytes(params: Sequence[Any]) -> tuple[Any, ...]:
    """Postgres text columns categorically cannot store a NUL (0x00) byte
    -- libpq raises ValueError outright on any string parameter containing
    one, not a soft truncation. SQLite has no such restriction, so content
    already written under SQLite (e.g. a PDF-extraction artifact in
    parsed_text -- verified live 2026-09-18 in the real seed export) can
    contain one. Stripped (not truncated at the NUL, the rest of the
    string is kept) uniformly for every write through this wrapper, so no
    individual call site needs its own NUL-handling logic.
    """
    return tuple(value.replace("\x00", "") if isinstance(value, str) else value for value in params)


class PgRow(tuple):
    """A tuple that ALSO supports string-keyed access and dict(row) --
    matches sqlite3.Row's dual positional/named behavior so
    inventory_db.row_to_dict()'s `dict(row)` and every `row[0]`-style
    positional access in this project work unchanged against Postgres.
    """

    _columns: tuple[str, ...]

    def __new__(cls, values: Sequence[Any], columns: tuple[str, ...]) -> "PgRow":
        row = super().__new__(cls, values)
        row._columns = columns
        return row

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, str):
            try:
                return super().__getitem__(self._columns.index(key))
            except ValueError:
                raise KeyError(key) from None
        return super().__getitem__(key)

    def keys(self) -> tuple[str, ...]:
        return self._columns


class PgCursorWrapper:
    """Wraps a real psycopg2 cursor: translates placeholders in, wraps
    rows out. Everything else (fetchone/fetchall/rowcount/description/
    close) passes straight through to the real cursor.
    """

    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.lastrowid: int | None = None  # never set automatically -- see module docstring

    def execute(self, sql: str, params: Sequence[Any] = ()) -> "PgCursorWrapper":
        stripped = sql.strip()
        if stripped.upper().startswith("PRAGMA"):
            return self  # no-op -- see module docstring
        # psycopg2 treats an empty tuple `()` differently from `None`:
        # passing `()` still tells it "do %-style substitution", so any
        # LITERAL `%` in the query (e.g. a LIKE pattern like '%.doc') gets
        # parsed as a format directive and blows up with "tuple index out
        # of range" since there's nothing in the (empty) tuple to
        # substitute. `None` (psycopg2's "no parameters" convention) skips
        # substitution entirely, leaving literal `%` characters alone --
        # matching sqlite3.Connection.execute()'s behavior, where a bare
        # query with no `?` placeholders never touches `%` at all.
        has_params = bool(params)
        self._cursor.execute(_translate_sql(sql, has_params), _strip_nul_bytes(params) if has_params else None)
        return self

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> "PgCursorWrapper":
        # executemany is only ever called with actual per-row values in
        # this project (see backend/inventory_db.seed_inventory_if_empty(),
        # the only caller) -- has_params=True unconditionally, matching
        # every real call site.
        self._cursor.executemany(
            _translate_sql(sql, has_params=True), [_strip_nul_bytes(params) for params in seq_of_params]
        )
        return self

    def _columns(self) -> tuple[str, ...]:
        return tuple(col.name for col in (self._cursor.description or ()))

    def fetchone(self) -> PgRow | None:
        row = self._cursor.fetchone()
        return None if row is None else PgRow(row, self._columns())

    def fetchall(self) -> list[PgRow]:
        columns = self._columns()
        return [PgRow(row, columns) for row in self._cursor.fetchall()]

    def __iter__(self):
        columns = self._columns()
        for row in self._cursor:
            yield PgRow(row, columns)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self) -> None:
        self._cursor.close()


class PgConnectionWrapper:
    """Wraps a real psycopg2 connection so `conn.execute(...)` works the
    same way sqlite3.Connection.execute(...) does (opens a cursor, runs
    the statement, returns something fetchable) -- this project's code
    calls `.execute()` directly on the connection object throughout, never
    `.cursor()` first.
    """

    dialect = "postgres"
    """Duck-typed marker so call sites that need genuinely different SQL
    per engine (json_each vs jsonb_array_elements_text, GROUP_CONCAT vs
    STRING_AGG, etc -- see docs/postgres_migration_notes.md's 5-item table)
    can branch on `getattr(conn, "dialect", "sqlite") == "postgres"`
    without importing this module (and therefore psycopg2) just to check.
    A plain sqlite3.Connection has no such attribute, so the getattr
    default covers it.
    """

    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, sql: str, params: Sequence[Any] = ()) -> PgCursorWrapper:
        cursor = PgCursorWrapper(self._connection.cursor())
        cursor.execute(sql, params)
        return cursor

    def executemany(self, sql: str, seq_of_params: Sequence[Sequence[Any]]) -> PgCursorWrapper:
        cursor = PgCursorWrapper(self._connection.cursor())
        cursor.executemany(sql, seq_of_params)
        return cursor

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def _iter_statements(sql: str):
    """Split a migration file into individual statements. Reuses
    sqlite3.complete_statement() -- purely lexical (tracks quotes/comments/
    `;`), not tied to SQLite semantics, so it works fine on the Postgres-
    dialect migration files too. Kept as its own function (duplicated from
    backend/inventory_db.py's identical one) rather than imported from
    there, so this module never needs `backend.inventory_db` as a
    dependency just for one helper.
    """
    import sqlite3  # stdlib, always available -- not a real sqlite dependency here, see docstring

    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                yield statement
            buffer = ""
    if buffer.strip():
        raise ValueError("Incomplete trailing SQL statement in migration file")


def run_migrations_pg(conn: PgConnectionWrapper, migrations_dir) -> None:
    """Postgres counterpart to backend/inventory_db.run_migrations() --
    same contract (filename-ordered, one transaction per file, recorded in
    schema_migrations), reading from `migrations_dir` (pass
    backend/inventory_migrations_pg/, produced by
    scripts/translate_migrations_to_postgres.py -- NOT backend/
    inventory_migrations/, which is SQLite dialect and would fail on
    `SERIAL`-incompatible `AUTOINCREMENT` etc).
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
        )
        """
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    if not migrations_dir.exists():
        return
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        statements = list(_iter_statements(path.read_text(encoding="utf-8")))
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()


@contextmanager
def get_pg_connection(dsn: str):
    """Same commit-on-success/rollback-on-exception/always-close contract
    as backend/inventory_db.get_inventory_connection() and backend/
    db.get_connection() -- a drop-in replacement shape, not just a
    similar-looking one.
    """
    raw_connection = psycopg2.connect(dsn)
    connection = PgConnectionWrapper(raw_connection)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
