-- 0006_pg_product_search.sql  (Postgres only -- copied verbatim into
-- backend/inventory_migrations_pg/ by scripts/translate_migrations_to_postgres.py)
--
-- Server-side product search for the ~130k-product catalogue:
--   * product_embeddings: BGE-M3 vectors computed offline on the operator's
--     PC (scripts/build_product_embeddings.py) and uploaded by
--     scripts/sync_to_production.py; backend/services/rag_service.py does
--     nearest-neighbour search here instead of embedding every product at
--     startup. halfvec keeps it at ~2 KB/row instead of 4 KB.
--   * trigram index so the product list's keyword filter (ILIKE '%kw%')
--     doesn't have to scan the whole table for 3+ character keywords.
-- SQLite has neither extension; locally rag_service reads the same vectors
-- from backend/data/product_embeddings/ instead.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS product_embeddings (
    product_db_id INTEGER PRIMARY KEY REFERENCES insurance_products(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    embedding halfvec(1024) NOT NULL,
    updated_at TEXT DEFAULT (to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE INDEX IF NOT EXISTS idx_product_embeddings_hnsw
    ON product_embeddings USING hnsw (embedding halfvec_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_products_name_trgm
    ON insurance_products USING gin (product_name gin_trgm_ops);
