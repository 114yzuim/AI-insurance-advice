-- AUTO-GENERATED from backend/inventory_migrations/0003_document_snapshots_unique.sql by
-- scripts/translate_migrations_to_postgres.py -- do not hand-edit, re-run that
-- script instead after changing the source SQLite migration.

-- 0003_document_snapshots_unique.sql
--
-- document_snapshots had no uniqueness constraint at all, so re-running a
-- downloader against the same document_registry row could insert a
-- duplicate snapshot row every time even when the downloaded content
-- (checksum) hadn't changed. This is the DB-level backstop for the
-- idempotency scripts/download_ib_documents.py already implements at the
-- application level (checking before inserting) -- belt and suspenders,
-- and it protects any other future writer of this table too.
--
-- A partial index (only when checksum is non-empty) rather than a plain
-- UNIQUE column constraint, because a failed download attempt might
-- legitimately be recorded with an empty checksum and there's no reason to
-- cap those at one per document_registry row.

CREATE UNIQUE INDEX IF NOT EXISTS ux_document_snapshots_registry_checksum
    ON document_snapshots(document_registry_id, checksum)
    WHERE checksum != '';
