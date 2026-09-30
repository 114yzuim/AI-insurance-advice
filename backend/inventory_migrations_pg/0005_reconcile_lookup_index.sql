-- AUTO-GENERATED from backend/inventory_migrations/0005_reconcile_lookup_index.sql by
-- scripts/translate_migrations_to_postgres.py -- do not hand-edit, re-run that
-- script instead after changing the source SQLite migration.

-- 0005_reconcile_lookup_index.sql
--
-- scripts/reconcile_source_records.py looks up the product_versions row for
-- each source record by primary_source_record_id. Without an index that is
-- a full scan per record -- fine for the first few hundred TII/IB records,
-- quadratic (hours) once the full ~128k-record TII index is imported.

CREATE INDEX IF NOT EXISTS idx_product_versions_primary_record ON product_versions(primary_source_record_id);
CREATE INDEX IF NOT EXISTS idx_products_source ON insurance_products(source, product_id);
