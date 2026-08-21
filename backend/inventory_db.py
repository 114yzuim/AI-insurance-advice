import json
import pathlib
import sqlite3
import gzip
from contextlib import contextmanager

DB_PATH = pathlib.Path(__file__).parent / "insurance_inventory.db"
SEED_PATH = pathlib.Path(__file__).parent / "data" / "inventory_seed.json.gz"

_JSON_COLS = {"former_names", "download_urls", "metadata"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS insurance_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('life', 'property', 'reinsurance')),
    status TEXT NOT NULL DEFAULT 'active',
    former_names TEXT NOT NULL DEFAULT '[]',
    official_url TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insurance_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    company_id INTEGER REFERENCES insurance_companies(id),
    company_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他',
    currency TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',
    source TEXT NOT NULL DEFAULT 'existing_crawl',
    source_url TEXT DEFAULT '',
    final_source_url TEXT DEFAULT '',
    url_status TEXT NOT NULL DEFAULT 'unknown',
    document_status TEXT NOT NULL DEFAULT 'unknown',
    is_historical INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}',
    scraped_at TEXT,
    imported_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(product_id, company_name)
);

CREATE TABLE IF NOT EXISTS policy_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_db_id INTEGER NOT NULL REFERENCES insurance_products(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL DEFAULT 'terms',
    title TEXT DEFAULT '',
    pdf_url TEXT NOT NULL,
    final_pdf_url TEXT DEFAULT '',
    local_path TEXT DEFAULT '',
    checksum TEXT DEFAULT '',
    pdf_status TEXT NOT NULL DEFAULT 'unknown',
    text_status TEXT NOT NULL DEFAULT 'pending',
    parsed_text TEXT DEFAULT '',
    downloaded_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(product_db_id, pdf_url)
);

CREATE TABLE IF NOT EXISTS product_link_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_db_id INTEGER NOT NULL REFERENCES insurance_products(id) ON DELETE CASCADE,
    source_url TEXT DEFAULT '',
    source_status TEXT DEFAULT '',
    source_result TEXT NOT NULL DEFAULT 'unknown',
    source_content_type TEXT DEFAULT '',
    final_source_url TEXT DEFAULT '',
    pdf_url TEXT DEFAULT '',
    pdf_status TEXT DEFAULT '',
    pdf_result TEXT NOT NULL DEFAULT 'unknown',
    pdf_content_type TEXT DEFAULT '',
    final_pdf_url TEXT DEFAULT '',
    error TEXT DEFAULT '',
    checked_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_company ON insurance_products(company_name);
CREATE INDEX IF NOT EXISTS idx_products_category ON insurance_products(category);
CREATE INDEX IF NOT EXISTS idx_products_status ON insurance_products(status, url_status, document_status);
CREATE INDEX IF NOT EXISTS idx_documents_product ON policy_documents(product_db_id);
CREATE INDEX IF NOT EXISTS idx_audits_product ON product_link_audits(product_db_id, checked_at);

CREATE TABLE IF NOT EXISTS policy_document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES policy_documents(id) ON DELETE CASCADE,
    product_db_id INTEGER NOT NULL REFERENCES insurance_products(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON policy_document_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_product ON policy_document_chunks(product_db_id);
CREATE INDEX IF NOT EXISTS idx_chunks_text ON policy_document_chunks(text);

CREATE TABLE IF NOT EXISTS insurance_profiles (
    id TEXT PRIMARY KEY,
    owner_name TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT '本人',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customer_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES insurance_profiles(id) ON DELETE CASCADE,
    product_id TEXT DEFAULT '',
    company_name TEXT NOT NULL,
    policy_name TEXT NOT NULL,
    policy_no TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT '主約',
    status TEXT NOT NULL DEFAULT '有效',
    annual_premium REAL NOT NULL DEFAULT 0,
    effective_date TEXT DEFAULT '',
    source_document_id INTEGER REFERENCES policy_documents(id),
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customer_policy_coverages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL REFERENCES customer_policies(id) ON DELETE CASCADE,
    coverage_key TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    UNIQUE(policy_id, coverage_key)
);

CREATE TABLE IF NOT EXISTS customer_policy_riders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL REFERENCES customer_policies(id) ON DELETE CASCADE,
    rider_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_policy_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES insurance_profiles(id) ON DELETE CASCADE,
    policy_id INTEGER REFERENCES customer_policies(id) ON DELETE SET NULL,
    original_filename TEXT NOT NULL,
    local_path TEXT NOT NULL,
    content_type TEXT DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    ocr_status TEXT NOT NULL DEFAULT 'pending',
    extracted_text TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_customer_policies_profile ON customer_policies(profile_id);
CREATE INDEX IF NOT EXISTS idx_customer_policies_company ON customer_policies(company_name);
CREATE INDEX IF NOT EXISTS idx_customer_policy_uploads_profile ON customer_policy_uploads(profile_id);
"""


def init_inventory_db() -> None:
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript(_SCHEMA)
        seed_inventory_if_empty(conn)
        conn.commit()


def seed_inventory_if_empty(conn: sqlite3.Connection) -> None:
    if not SEED_PATH.exists():
        return
    product_count = conn.execute("SELECT COUNT(*) FROM insurance_products").fetchone()[0]
    if product_count:
        return

    with gzip.open(SEED_PATH, "rt", encoding="utf-8") as seed_file:
        payload = json.load(seed_file)

    for table in ("insurance_companies", "insurance_products", "policy_documents", "policy_document_chunks"):
        rows = payload.get(table, [])
        if not rows:
            continue
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        conn.executemany(
            f"INSERT OR REPLACE INTO {table} ({column_sql}) VALUES ({placeholders})",
            [[row.get(column) for column in columns] for row in rows],
        )


@contextmanager
def get_inventory_connection():
    init_inventory_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in _JSON_COLS:
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return data
