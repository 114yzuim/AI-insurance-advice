-- 0008_product_attributes.sql
--
-- Structured product facts extracted from each product's own clause / DM
-- text by scripts/extract_product_attributes.py (run on the operator's PC:
-- regex rules + a local Ollama model, no paid API). One row per product.
-- `attributes` is JSON (see that script's module docstring for the shape);
-- `field_methods` records, per field, whether a rule or the model produced
-- it, so low-trust fields can be filtered or re-checked later.

CREATE TABLE IF NOT EXISTS product_attributes (
    product_db_id INTEGER PRIMARY KEY REFERENCES insurance_products(id) ON DELETE CASCADE,
    attributes TEXT NOT NULL DEFAULT '{}',
    field_methods TEXT NOT NULL DEFAULT '{}',
    source_document_ids TEXT NOT NULL DEFAULT '[]',
    source_text_hash TEXT NOT NULL DEFAULT '',
    extractor_version TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    extracted_at TEXT DEFAULT (datetime('now'))
);
