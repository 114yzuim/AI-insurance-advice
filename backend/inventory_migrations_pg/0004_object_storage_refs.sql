-- AUTO-GENERATED from backend/inventory_migrations/0004_object_storage_refs.sql by
-- scripts/translate_migrations_to_postgres.py -- do not hand-edit, re-run that
-- script instead after changing the source SQLite migration.

-- 0004_object_storage_refs.sql
--
-- Nullable columns only, per this phase's constraint: existing rows are
-- never backfilled, and nothing existing reads/writes these until
-- scripts/download_ib_documents.py starts populating them going forward
-- (see that script's "also write to object storage" step). The document's
-- durable identity stays the existing `checksum` column -- these are only
-- a pointer to where that checksum's bytes ALSO live, in
-- scripts/object_storage.py's store (local file today, S3-compatible
-- later without another migration -- the column just holds whatever
-- ObjectRef.uri that backend produced).

ALTER TABLE document_snapshots ADD COLUMN object_store_uri TEXT DEFAULT '';
ALTER TABLE document_snapshots ADD COLUMN object_store_key TEXT DEFAULT '';
