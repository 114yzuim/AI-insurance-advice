# Moving `backend/insurance_inventory.db` (SQLite) to Postgres

Scope: this covers the **crawler/inventory pipeline's** database
(`backend/inventory_db.py`, `backend/insurance_inventory.db`) -- the one
`scripts/*.py` reads and writes throughout the four phases so far. It does
**not** cover `backend/db.py` (`backend/advisor.db`, the separate DB behind
the customer-facing health-check/claim-prep features) or `backend/
db_init.py` -- those would need the same treatment separately, and aren't
audited here.

## Status: the switch is wired in and working, tested end-to-end

`backend/inventory_db.get_inventory_connection()` -- the single entry point
every one of this project's ~25 scripts already uses -- now picks its
backend based on the `DATABASE_URL` env var:

```bash
# unset (default): exactly the SQLite behavior this project has always had
python scripts/report_policy_data_readiness.py

# set: the SAME script, unmodified, runs against Postgres instead
DATABASE_URL="postgresql://user:pass@host:5432/dbname" python scripts/report_policy_data_readiness.py
```

This was verified against a real `postgres:16-alpine` container, from a
completely empty database, through the full real pipeline -- not just
toy examples:

- **Migrations**: `get_inventory_connection()` runs
  `backend/inventory_migrations_pg/*.sql` (via `backend/pg_compat.
  run_migrations_pg()`) the same way the SQLite path runs `backend/
  inventory_migrations/*.sql` -- 4/4 applied cleanly, tracked in a real
  `schema_migrations` table.
- **Seed loading**: `seed_inventory_if_empty()` (unmodified logic, one
  dialect branch for the `INSERT OR REPLACE` → `ON CONFLICT` difference)
  loaded the real seed export -- **2,192 products, 37,381 chunks** -- into
  Postgres from scratch through the exact same code path used for SQLite.
- **`inventory_repository.py`'s core functions**, completely unmodified
  except the `RETURNING id` fix (see below): `ensure_default_sources`,
  `create_crawl_run`, `upsert_source_product_record`,
  `upsert_document_registry`, `upsert_document_snapshot` -- all verified
  live against Postgres, correct integer ids at every step, foreign keys
  respected.
- **`scripts/report_policy_data_readiness.py`, `scripts/
  check_deployment_readiness.py`, `scripts/report_inventory_quality.py`,
  `scripts/import_inventory.py`, `scripts/report_requested_company_
  coverage.py`** -- all run against the real 2,192-product Postgres
  dataset with correct output (spot-checked: `STRING_AGG` producing an
  88-product concatenation, `jsonb_array_elements_text` correctly matching
  a company by its former name "中國人壽" → 凱基人壽).
- **Full SQLite test suite (72 tests) re-run after every fix** -- zero
  regressions on the default (SQLite) path throughout.

## What needed a real code fix (not a shim) -- and is now DONE

- **`cursor.lastrowid`** (SQLite-only) → every INSERT needing the new
  row's id now does `INSERT ... RETURNING id` + `cursor.fetchone()[0]`.
  Works identically on SQLite 3.35+ (this project's SQLite is 3.50.4) and
  Postgres -- not a per-dialect branch, one code path for both. 7 call
  sites fixed: `scripts/inventory_repository.py` (`create_crawl_run`,
  `upsert_source_product_record`, `upsert_document_registry`,
  `upsert_product_family`, `upsert_product_version`,
  `upsert_document_snapshot`) and `scripts/sync_document_registry_to_
  policy_documents.py` (`_find_or_create_product`).
- **`json_each(col)`** (SQLite JSON1, no Postgres equivalent) → dialect
  branch to `jsonb_array_elements_text(col::jsonb)`, keyed on
  `getattr(conn, "dialect", "sqlite")`. Fixed in `scripts/
  import_inventory.py`'s `company_id_for()` and `scripts/
  report_requested_company_coverage.py`'s `fetch_company()`.
- **`GROUP_CONCAT(expr, sep)`** → `STRING_AGG(expr, sep)` (same argument
  order, just a different name) -- dialect branch in `scripts/
  report_inventory_quality.py`, 2 call sites.
- **`INSERT OR REPLACE INTO table (...)`** → `INSERT ... ON CONFLICT (id)
  DO UPDATE SET col = excluded.col, ...` -- fixed in `backend/
  inventory_db.py`'s `seed_inventory_if_empty()`.
- **`PRAGMA table_info(x)`** → `SELECT column_name, data_type FROM
  information_schema.columns WHERE table_name = ?` -- fixed via a new
  `_table_columns_with_types()` helper in `scripts/check_deployment_
  readiness.py`, used by its `no_raw_blobs_in_db` check (which also now
  flags Postgres's `bytea` type alongside SQLite's `BLOB`).
- **`PRAGMA foreign_keys = ON`** -- no fix needed, `backend/pg_compat.py`'s
  `PgCursorWrapper.execute()` silently no-ops any `PRAGMA` statement
  (Postgres always enforces FKs; there's nothing to turn on).

## Two more real bugs found only by actually testing against Postgres

Not in the original audit -- found live, both fixed:

1. **`idx_chunks_text` (a plain btree index on the full
   `policy_document_chunks.text` column) makes INSERTs fail outright on
   Postgres** once a chunk is long enough: Postgres caps a single btree
   index entry at ~2704 bytes, and a ~1800-character Traditional Chinese
   chunk (3 bytes/char in UTF-8) blows past that. SQLite has no such
   limit, so this was invisible there. Confirmed via grep that nothing
   anywhere queries this column by equality/prefix -- the index is dead
   weight even on SQLite. Fixed by dropping it specifically in
   `scripts/translate_migrations_to_postgres.py`'s output (SQLite's own
   migration file is untouched).
2. **psycopg2's `%`-style parameter substitution treats an ordinary LIKE
   pattern as a format string.** `'%guide%'` contains `%g`, a valid
   Python/C conversion specifier (like `%s`, `%d`) -- when real params are
   being substituted, psycopg2 scans the WHOLE query text for these and
   tries to consume an argument for each one it finds, so `'%guide%'`
   silently ate an argument slot that wasn't there and crashed with
   `IndexError: tuple index out of range` (verified live on `scripts/
   report_inventory_quality.py`'s `'%guide%'`/`'%導讀%'` patterns). Two
   related fixes in `backend/pg_compat.py`:
   - literal `%` in the SQL text is now escaped to `%%` before handing the
     query to psycopg2, but **only when real params are being passed** --
     escaping when there are none would corrupt the literal LIKE pattern
     sent to Postgres, since no substitution happens in that case at all.
   - a query with **zero params** now passes `vars=None` to psycopg2
     rather than an empty tuple `()` -- psycopg2 treats `()` as "yes,
     please do %-substitution" (and then has nothing to substitute),
     while `None` means "no substitution at all", matching how
     `sqlite3.Connection.execute()` behaves with no `?` placeholders.
3. **NUL bytes (`\x00`) in a TEXT value are rejected outright by Postgres**
   (`ValueError` from libpq, not a soft truncation) -- SQLite has no such
   restriction. Found live in the real seed export's `parsed_text` data (a
   PDF-extraction artifact, not something to fix at the source this
   round). Fixed generically in `backend/pg_compat.py`'s `_strip_nul_
   bytes()`, applied to every parameter on every `execute()`/
   `executemany()` through the wrapper -- not just the seed loader, so any
   future write with an embedded NUL is handled the same way, not just
   this one historical case.

## The recommended approach: shim, not ORM, not a rewrite

Three options were considered and this is why (2) was chosen:

1. **Rewrite every script to psycopg2-native SQL.** Rejected: ~25 files,
   hundreds of `?`-placeholder call sites, for a mechanical
   find-and-replace a shim already does correctly and more safely.
2. **A thin DB-API compatibility shim (`backend/pg_compat.py`).** Chosen.
   Under 300 lines, fully reviewed, and now proven against real Postgres
   at real data volume (2,192 products) for the functions this project's
   pipeline calls most.
3. **Introduce an ORM (SQLAlchemy, etc).** Rejected: every script here is
   hand-tuned SQL built and verified against real IB/TII data one query at
   a time across four phases. An ORM rewrite is a much larger, riskier
   change than this problem needs.

## What's still NOT done (deliberately, not an oversight)

- **No cutover decision has been made.** `DATABASE_URL` unset still means
  SQLite, unconditionally -- this is infrastructure that's ready to use
  when the project decides to point staging at Postgres, not something
  that changed the default.
- **`backend/db.py` / `backend/advisor.db`** (the customer-facing app's
  separate database) hasn't been touched or audited.
- **No bulk data migration tooling** (SQLite → Postgres for a database
  that's not empty) exists -- everything above was tested against either
  an empty Postgres DB (migrations + seed-from-scratch) or the seed export
  file, not a live copy of the real `backend/insurance_inventory.db`
  currently in this repo. Copying THAT specific database's current
  contents (as opposed to the seed export) into Postgres is a separate,
  not-yet-attempted step.
- **Connection pooling, retry/backoff on transient Postgres connection
  errors, and TLS/`sslmode` configuration** for a real Railway Postgres
  instance aren't addressed -- `pg_compat.get_pg_connection()` is a bare
  `psycopg2.connect(dsn)`.
- **`backend/pg_compat.py` is dependency-lazy but not dependency-optional
  in `requirements.txt`** -- `psycopg2-binary` is now listed there (see
  its own comment) so it's available when `DATABASE_URL` is set, but
  nothing currently makes it truly optional at install time (e.g. an
  extras group). Low priority given it's one line and installs cleanly on
  every platform this project targets.

## Suggested next steps, in order

1. Decide when Postgres actually becomes the target for staging (see
   docs/production_deployment_readiness.md) -- this phase made it
   possible, not mandatory.
2. If/when that happens: point a real Railway Postgres instance's
   `DATABASE_URL` at a fresh deploy and re-run `scripts/
   check_deployment_readiness.py` + `scripts/run_staging_smoke_test.py`
   against it, the same way this phase did locally, before trusting it
   with real crawl traffic.
3. Plan the actual data migration for the CURRENT `backend/
   insurance_inventory.db` (not the seed export) once a Postgres target is
   decided -- export/import tooling for that specific transition doesn't
   exist yet.
