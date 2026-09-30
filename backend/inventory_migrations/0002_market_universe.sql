-- 0002_market_universe.sql
--
-- Market-universe layer: a central staging + reconciliation area that sits
-- in front of the existing insurance_products / policy_documents /
-- policy_document_chunks tables. It is additive only -- nothing here alters
-- or reads from those tables, and no existing table is touched.
--
-- Pipeline this schema supports (see backend/inventory_migrations/README.md
-- for the general migration rules):
--
--   TII / IB source records
--         v
--   source_product_records   (raw-ish, one row per source's view of a product)
--         v
--   product_families / product_versions   (reconciled, canonical)
--         v
--   document_registry -> document_snapshots   (what documents should exist,
--                                               and what we actually have)
--         v
--   reconciliation_findings   (where sources disagree or something's missing)
--
-- All statements are idempotent (CREATE TABLE/INDEX IF NOT EXISTS) so this
-- migration is safe to re-run and safe against a database that has never
-- seen it before.

CREATE TABLE IF NOT EXISTS inventory_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,              -- 'tii' | 'ib_disclosure' | 'company_site'
    name TEXT NOT NULL,
    authority_level TEXT NOT NULL DEFAULT 'secondary',  -- e.g. 'central_registry' | 'regulatory_disclosure' | 'primary'
    base_url TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES inventory_sources(id) ON DELETE CASCADE,
    run_type TEXT NOT NULL DEFAULT 'import',   -- 'import' | 'refresh' | 'reconcile' | 'audit'
    status TEXT NOT NULL DEFAULT 'running',    -- 'running' | 'succeeded' | 'failed'
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT,
    records_seen INTEGER NOT NULL DEFAULT 0,
    records_changed INTEGER NOT NULL DEFAULT 0,
    error TEXT DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_source ON crawl_runs(source_id, started_at);

CREATE TABLE IF NOT EXISTS source_product_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES inventory_sources(id) ON DELETE CASCADE,
    crawl_run_id INTEGER REFERENCES crawl_runs(id) ON DELETE SET NULL,
    source_product_id TEXT NOT NULL,      -- the source's own id (TII productId, IB reference no, ...)
    source_product_url TEXT DEFAULT '',
    company_name TEXT DEFAULT '',
    product_code TEXT DEFAULT '',
    product_name TEXT DEFAULT '',
    insurance_category TEXT DEFAULT '',   -- raw, as printed by the source (財產保險/人身保險/...)
    insurance_type TEXT DEFAULT '',       -- raw, as printed by the source (傳統型壽險/健康保險/...)
    sale_start_date TEXT DEFAULT '',
    sale_end_date TEXT DEFAULT '',
    approval_date TEXT DEFAULT '',
    approval_number TEXT DEFAULT '',
    filing_number TEXT DEFAULT '',
    review_method TEXT DEFAULT '',
    raw_payload TEXT NOT NULL DEFAULT '{}',   -- full source record, JSON text
    payload_hash TEXT NOT NULL DEFAULT '',    -- sha256 of a canonical (sorted-keys) encoding of raw_payload
    first_seen_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_id, source_product_id)
);

CREATE INDEX IF NOT EXISTS idx_source_records_company ON source_product_records(company_name);
CREATE INDEX IF NOT EXISTS idx_source_records_product_code ON source_product_records(product_code);
CREATE INDEX IF NOT EXISTS idx_source_records_last_seen ON source_product_records(source_id, last_seen_at);

CREATE TABLE IF NOT EXISTS product_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_company_name TEXT NOT NULL,
    canonical_product_name TEXT NOT NULL,
    normalized_key TEXT UNIQUE NOT NULL,   -- deterministic slug of (company, product name) used for matching
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_product_families_company ON product_families(canonical_company_name);

CREATE TABLE IF NOT EXISTS product_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_family_id INTEGER REFERENCES product_families(id) ON DELETE SET NULL,
    primary_source_record_id INTEGER REFERENCES source_product_records(id) ON DELETE SET NULL,
    canonical_company_name TEXT NOT NULL,
    canonical_product_name TEXT NOT NULL,
    product_code TEXT DEFAULT '',
    insurance_category TEXT DEFAULT '',
    insurance_type TEXT DEFAULT '',
    sale_start_date TEXT DEFAULT '',
    sale_end_date TEXT DEFAULT '',
    approval_date TEXT DEFAULT '',
    approval_number TEXT DEFAULT '',
    filing_number TEXT DEFAULT '',
    review_method TEXT DEFAULT '',
    version_label TEXT DEFAULT '',
    canonical_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',  -- see reconciliation_findings.finding_code vocabulary
    match_confidence REAL NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_product_versions_family ON product_versions(product_family_id);
CREATE INDEX IF NOT EXISTS idx_product_versions_company ON product_versions(canonical_company_name);
CREATE INDEX IF NOT EXISTS idx_product_versions_status ON product_versions(canonical_status);

CREATE TABLE IF NOT EXISTS document_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_version_id INTEGER REFERENCES product_versions(id) ON DELETE CASCADE,
    source_record_id INTEGER REFERENCES source_product_records(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT '',        -- inventory_sources.code, denormalized for quick filtering
    document_type TEXT NOT NULL DEFAULT 'OTHER',  -- see scripts/sources/tii/source.py DocumentType
    title TEXT DEFAULT '',
    url TEXT NOT NULL,
    final_url TEXT DEFAULT '',
    url_status TEXT NOT NULL DEFAULT 'unknown',
    availability_status TEXT NOT NULL DEFAULT 'UNKNOWN',  -- AVAILABLE | NOT_LISTED | BROKEN_LINK | ... (Phase 4 vocabulary)
    source_document_id TEXT DEFAULT '',     -- e.g. TII's Open2.ashx `id` GUID
    metadata TEXT NOT NULL DEFAULT '{}',
    first_seen_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(source_record_id, url)
);

CREATE INDEX IF NOT EXISTS idx_document_registry_version ON document_registry(product_version_id);
CREATE INDEX IF NOT EXISTS idx_document_registry_source ON document_registry(source, document_type);

CREATE TABLE IF NOT EXISTS document_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_registry_id INTEGER NOT NULL REFERENCES document_registry(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    final_url TEXT DEFAULT '',
    content_type TEXT DEFAULT '',
    local_path TEXT DEFAULT '',
    checksum TEXT DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    downloaded_at TEXT,
    parser_status TEXT NOT NULL DEFAULT 'pending',
    parser_engine TEXT DEFAULT '',
    parser_version TEXT DEFAULT '',
    parsed_text TEXT DEFAULT '',
    tables_json TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_document_snapshots_registry ON document_snapshots(document_registry_id, created_at);

CREATE TABLE IF NOT EXISTS reconciliation_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_version_id INTEGER REFERENCES product_versions(id) ON DELETE CASCADE,
    source_record_id INTEGER REFERENCES source_product_records(id) ON DELETE CASCADE,
    finding_code TEXT NOT NULL,   -- VERIFIED | RECENT_PENDING | TII_ONLY | COMPANY_ONLY | IB_ONLY |
                                  -- DOCUMENT_MISSING | DOCUMENT_BROKEN | METADATA_CONFLICT | STALE_SOURCE | NEEDS_REVIEW
    severity TEXT NOT NULL DEFAULT 'info',   -- 'info' | 'warning' | 'error'
    status TEXT NOT NULL DEFAULT 'open',     -- 'open' | 'acknowledged' | 'resolved'
    evidence_json TEXT NOT NULL DEFAULT '{}',
    first_detected_at TEXT DEFAULT (datetime('now')),
    last_detected_at TEXT DEFAULT (datetime('now')),
    grace_until TEXT DEFAULT '',
    resolved_at TEXT DEFAULT '',
    resolution_note TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_version ON reconciliation_findings(product_version_id, status);
CREATE INDEX IF NOT EXISTS idx_reconciliation_code ON reconciliation_findings(finding_code, status);

CREATE TABLE IF NOT EXISTS document_expectation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insurance_category TEXT DEFAULT '',   -- '' means "any"
    insurance_type TEXT DEFAULT '',       -- '' means "any"
    product_role TEXT DEFAULT '',         -- '' means "any"; e.g. 'main' | 'rider' | 'endorsement'
    document_type TEXT NOT NULL,          -- see scripts/sources/tii/source.py DocumentType
    requirement_level TEXT NOT NULL DEFAULT 'expected',  -- 'required' | 'expected' | 'optional' | 'not_applicable'
    effective_from TEXT DEFAULT '',
    effective_to TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_doc_expectation_lookup
    ON document_expectation_rules(insurance_category, insurance_type, product_role);
