"""Push locally analyzed data to the production Postgres -- NEVER raw files.

Policy (agreed with the project owner): raw PDF/DOC/XLS/HTML stay on the
local machine (backend/data/); production only receives structured
products, document metadata, parsed text and chunks. File-pointer columns
(local_path, object_store_uri, object_store_key) are blanked in production so
nothing there references a file that doesn't exist.

Idempotent: rows are upserted by id and only rewritten when something
actually differs; chunks that no longer exist locally are removed from
production. Customer tables (customer_*, claim_cases, insurance_profiles) are
never touched.

Usage:
    PROD_DATABASE_URL=postgresql://... python scripts/sync_to_production.py --dry-run
    PROD_DATABASE_URL=postgresql://... python scripts/sync_to_production.py
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sqlite3
import struct
import sys
from pathlib import Path

import numpy as np
import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB = ROOT / "backend" / "insurance_inventory.db"
EMBEDDINGS_DIR = ROOT / "backend" / "data" / "product_embeddings"
sys.path.insert(0, str(ROOT / "backend"))

# FK-safe order.
TABLES = [
    "inventory_sources", "crawl_runs", "insurance_companies", "insurance_products",
    "source_product_records", "product_families", "product_versions",
    "document_registry", "document_snapshots", "policy_documents", "policy_document_chunks",
    "product_attributes",
]
# Tables keyed by something other than a SERIAL "id" (no sequence to bump).
PRIMARY_KEYS = {"product_attributes": "product_db_id"}
BLANKED = {
    "policy_documents": {"local_path"},
    "document_snapshots": {"local_path", "object_store_uri", "object_store_key"},
}


def _clean(value):
    return value.replace("\x00", "") if isinstance(value, str) else value


def _apply_migrations(prod_dsn: str) -> None:
    """Same migrations the backend applies on first connection -- run here
    too so a new table (e.g. product_embeddings) exists before we write it,
    even if the new backend hasn't been deployed yet."""
    from inventory_db import MIGRATIONS_DIR_PG
    from pg_compat import get_pg_connection, run_migrations_pg

    with get_pg_connection(prod_dsn) as conn:
        run_migrations_pg(conn, MIGRATIONS_DIR_PG)


def _halfvec_copy_payload(rows: list[tuple[int, str, str, np.ndarray]]) -> io.BytesIO:
    """Postgres binary COPY stream for (int4, text, text, halfvec) rows.
    ~2 KB per vector instead of ~7 KB as a text literal -- this is ~130k
    vectors on a home upload link. halfvec's binary form (pgvector
    halfvec_recv) is int16 dim, int16 unused, then dim big-endian float16."""
    buf = io.BytesIO()
    buf.write(b"PGCOPY\n\xff\r\n\x00" + struct.pack(">ii", 0, 0))
    for product_db_id, model, text_hash, vec in rows:
        model_b, hash_b = model.encode(), text_hash.encode()
        vec_b = struct.pack(">hh", len(vec), 0) + np.asarray(vec, dtype=">f2").tobytes()
        buf.write(struct.pack(">h", 4))
        buf.write(struct.pack(">ii", 4, product_db_id))
        buf.write(struct.pack(">i", len(model_b)) + model_b)
        buf.write(struct.pack(">i", len(hash_b)) + hash_b)
        buf.write(struct.pack(">i", len(vec_b)) + vec_b)
    buf.write(struct.pack(">h", -1))
    buf.seek(0)
    return buf


def _ensure_hnsw_index(pg) -> None:
    cur = pg.cursor()
    cur.execute("SELECT to_regclass('idx_product_embeddings_hnsw')")
    if cur.fetchone()[0] is not None:
        return
    print("  building HNSW index ...", flush=True)
    # Serial build in backend-local memory: a parallel build allocates
    # maintenance_work_mem in /dev/shm, which Railway's Postgres container
    # keeps tiny ("could not resize shared memory segment ... No space").
    cur.execute("SET max_parallel_maintenance_workers = 0")
    cur.execute("SET maintenance_work_mem = '1GB'")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_embeddings_hnsw ON product_embeddings USING hnsw (embedding halfvec_cosine_ops)"
    )
    pg.commit()


def sync_embeddings(pg, dry_run: bool) -> dict:
    meta_path = EMBEDDINGS_DIR / "meta.json"
    if not meta_path.exists():
        return {"skipped": "no local embeddings (run scripts/build_product_embeddings.py)"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    vectors = np.load(EMBEDDINGS_DIR / "embeddings.npy")
    cur = pg.cursor()
    cur.execute("SELECT product_db_id, text_hash FROM product_embeddings")
    prod = dict(cur.fetchall())
    todo = [
        (pid, meta["model"], h, vectors[i])
        for i, (pid, h) in enumerate(zip(meta["ids"], meta["text_hashes"]))
        if h and prod.get(pid) != h
    ]
    report = {"local_valid": sum(1 for h in meta["text_hashes"] if h), "prod_before": len(prod), "to_upload": len(todo)}
    if dry_run:
        return report
    if not todo:
        _ensure_hnsw_index(pg)
        return report

    # Bulk (re)loads are much faster with the HNSW index built once at the
    # end than maintained row by row.
    rebuild_index = len(todo) > 20000
    if rebuild_index:
        cur.execute("DROP INDEX IF EXISTS idx_product_embeddings_hnsw")
        pg.commit()
    cur.execute(
        "CREATE TEMP TABLE staging_embeddings (product_db_id int4, model text, text_hash text, embedding halfvec(1024)) ON COMMIT DROP"
    )  # lives until the commit after the INSERT below
    for start in range(0, len(todo), 10000):
        cur.copy_expert("COPY staging_embeddings FROM STDIN WITH (FORMAT BINARY)", _halfvec_copy_payload(todo[start : start + 10000]))
        print(f"  embeddings uploaded {min(start + 10000, len(todo))}/{len(todo)}", flush=True)
    cur.execute(
        """
        INSERT INTO product_embeddings (product_db_id, model, text_hash, embedding)
        SELECT s.product_db_id, s.model, s.text_hash, s.embedding
        FROM staging_embeddings s JOIN insurance_products p ON p.id = s.product_db_id
        ON CONFLICT (product_db_id) DO UPDATE
        SET model = excluded.model, text_hash = excluded.text_hash, embedding = excluded.embedding,
            updated_at = to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')
        """
    )
    pg.commit()  # keep the uploaded vectors even if the index build below fails
    _ensure_hnsw_index(pg)
    cur.execute("SELECT COUNT(*) FROM product_embeddings")
    report["prod_after"] = cur.fetchone()[0]
    return report


def sync(prod_dsn: str, dry_run: bool, skip_embeddings: bool = False, only_embeddings: bool = False,
         tables: list[str] | None = None) -> dict:
    if not dry_run:
        _apply_migrations(prod_dsn)
    src = sqlite3.connect(LOCAL_DB)
    src.row_factory = sqlite3.Row
    pg = psycopg2.connect(prod_dsn)
    cur = pg.cursor()
    report = {}
    for table in [] if only_embeddings else [t for t in TABLES if not tables or t in tables]:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        before = cur.fetchone()[0]
        report[table] = {"local": len(rows), "prod_before": before}
        if not rows or dry_run:
            continue
        cols = list(rows[0].keys())
        blank = BLANKED.get(table, set())
        values = [tuple("" if c in blank else _clean(r[c]) for c in cols) for r in rows]
        key = PRIMARY_KEYS.get(table, "id")
        update = [c for c in cols if c != key]
        sets = ", ".join(f"{c} = excluded.{c}" for c in update)
        differs = (
            f"({', '.join('t.' + c for c in update)}) IS DISTINCT FROM "
            f"({', '.join('excluded.' + c for c in update)})"
        )
        sql = (
            f"INSERT INTO {table} AS t ({', '.join(cols)}) VALUES %s "
            f"ON CONFLICT ({key}) DO UPDATE SET {sets} WHERE {differs}"
        )
        psycopg2.extras.execute_values(cur, sql, values, page_size=1000)
        if table == "policy_document_chunks":
            ids = [r["id"] for r in rows]
            cur.execute("DELETE FROM policy_document_chunks WHERE NOT (id = ANY(%s))", (ids,))
            report[table]["stale_removed"] = cur.rowcount
        if key == "id":
            cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), true)")
        pg.commit()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        report[table]["prod_after"] = cur.fetchone()[0]
        print(f"  {table}: {report[table]}", flush=True)
    cur.execute("SELECT to_regclass('product_embeddings')")
    if cur.fetchone()[0] and not skip_embeddings:
        report["product_embeddings"] = sync_embeddings(pg, dry_run)
    pg.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Only compare row counts, write nothing.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Sync tables only (e.g. while embeddings are still being computed).")
    parser.add_argument("--only-embeddings", action="store_true", help="Sync product_embeddings only.")
    parser.add_argument("--tables", nargs="+", choices=TABLES, help="Sync only these tables (e.g. product_attributes).")
    args = parser.parse_args()
    dsn = os.environ.get("PROD_DATABASE_URL")
    if not dsn:
        sys.exit("PROD_DATABASE_URL is required (never read from backend/.env, to avoid accidental production writes).")
    from urllib.parse import urlparse

    host = urlparse(dsn).hostname or ""
    if host in ("", "localhost", "127.0.0.1", "::1"):
        # e.g. an empty proxy endpoint pasted into the URL -- that would
        # silently target a local Postgres instead of production.
        sys.exit(f"PROD_DATABASE_URL has no production host (got {host!r}); refusing to sync.")
    print(json.dumps(sync(dsn, args.dry_run, args.skip_embeddings, args.only_embeddings, args.tables), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
