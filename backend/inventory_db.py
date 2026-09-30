import json
import os
import pathlib
import sqlite3
import gzip
from contextlib import closing, contextmanager
from threading import Lock

from dotenv import load_dotenv

DB_PATH = pathlib.Path(__file__).parent / "insurance_inventory.db"
SEED_PATH = pathlib.Path(__file__).parent / "data" / "inventory_seed.json.gz"
_INIT_LOCK = Lock()

# Loads backend/.env (DATABASE_URL) for every script that imports this module,
# not just the FastAPI app. A no-op if the file doesn't exist or the variable
# is already set in the real environment (as on Railway).
load_dotenv(pathlib.Path(__file__).parent / ".env")

MIGRATIONS_DIR = pathlib.Path(__file__).parent / "inventory_migrations"
MIGRATIONS_DIR_PG = pathlib.Path(__file__).parent / "inventory_migrations_pg"

# When set, get_inventory_connection() uses Postgres via backend/pg_compat.py
# (production: the ~130k-product catalogue lives there); otherwise the SQLite
# file above, exactly as before. psycopg2 is imported lazily, only on that path.
DATABASE_URL_ENV_VAR = "DATABASE_URL"
_MIGRATE_LOCK = Lock()
_MIGRATED_PATHS: set[str] = set()

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

CREATE TABLE IF NOT EXISTS claim_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL REFERENCES insurance_profiles(id) ON DELETE CASCADE,
    client_id TEXT DEFAULT '',
    owner_name TEXT DEFAULT '',
    scenario TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT '文件整理中',
    medical_expense_total REAL NOT NULL DEFAULT 0,
    estimated_total REAL NOT NULL DEFAULT 0,
    high_confidence_total REAL NOT NULL DEFAULT 0,
    review_total REAL NOT NULL DEFAULT 0,
    document_summary TEXT NOT NULL DEFAULT '{}',
    required_documents TEXT NOT NULL DEFAULT '[]',
    companies TEXT NOT NULL DEFAULT '[]',
    notes TEXT DEFAULT '',
    next_follow_up_date TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_claim_cases_profile ON claim_cases(profile_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_claim_cases_client ON claim_cases(client_id, updated_at);
"""


def init_inventory_db() -> None:
    # Parallel initial requests must not race while importing the seed.
    # sqlite3's transaction context alone does not close the connection.
    with _INIT_LOCK, closing(sqlite3.connect(str(DB_PATH), timeout=30)) as conn:
        conn.executescript(_SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        seed_inventory_if_empty(conn)
        conn.commit()


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _iter_statements(sql: str):
    """Split a migration file into statements (sqlite3.complete_statement
    understands strings/comments), so each file runs in one transaction --
    executescript() would commit part-way and could leave it half-applied."""
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


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply every inventory_migrations/*.sql not yet recorded in
    schema_migrations, in filename order, one transaction per file. They add
    the market-universe tables (source records, document registry, product
    attributes, ...) on top of _SCHEMA; 0001 repeats _SCHEMA with IF NOT
    EXISTS, so it is a no-op on a database init_inventory_db() created."""
    _ensure_migrations_table(conn)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    if not MIGRATIONS_DIR.exists():
        return
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        statements = list(_iter_statements(path.read_text(encoding="utf-8")))
        conn.execute("BEGIN")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()


def _ensure_sqlite_migrations() -> None:
    """Run the migrations once per process per database file, after
    init_inventory_db(); serialized so parallel first requests can't both
    apply the same file."""
    key = str(DB_PATH)
    if key in _MIGRATED_PATHS:
        return
    with _MIGRATE_LOCK:
        if key in _MIGRATED_PATHS:
            return
        with closing(sqlite3.connect(key, timeout=30, isolation_level=None)) as conn:
            run_migrations(conn)
        _MIGRATED_PATHS.add(key)


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
        values = [[row.get(column) for column in columns] for row in rows]
        # `INSERT OR REPLACE` is SQLite-only; on Postgres (pg_compat) use an
        # explicit conflict target -- seed dumps always carry the `id` PK.
        if getattr(conn, "dialect", "sqlite") == "postgres" and "id" in columns:
            update_columns = [c for c in columns if c != "id"]
            set_sql = ", ".join(f"{c} = excluded.{c}" for c in update_columns)
            sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT (id) DO UPDATE SET {set_sql}"
        else:
            sql = f"INSERT OR REPLACE INTO {table} ({column_sql}) VALUES ({placeholders})"
        conn.executemany(sql, values)


@contextmanager
def get_inventory_connection():
    """SQLite by default; Postgres when DATABASE_URL is set (production).
    Callers just use conn.execute(...) on either -- pg_compat translates the
    SQLite-style placeholders and rows."""
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if database_url:
        import sys

        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from pg_compat import get_pg_connection, run_migrations_pg

        with get_pg_connection(database_url) as conn:
            run_migrations_pg(conn, MIGRATIONS_DIR_PG)
            seed_inventory_if_empty(conn)
            yield conn
        return

    init_inventory_db()
    _ensure_sqlite_migrations()
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
