"""Bridge the new market-universe tables (Phase 2) to the pre-existing
insurance_products / policy_documents tables the company-crawl pipeline
(scripts/adapters/*.py) and RAG chunking (scripts/parse_pdf_snapshots.py)
already read.

Why this exists
-----------------
Since Phase 2, downloaded/resolved documents live in document_registry +
document_snapshots (new). But the RAG pipeline and (per grep) anything else
in this codebase that reads policy_documents/policy_document_chunks has no
idea those tables exist -- they only ever read insurance_products/
policy_documents. Without this bridge, TII/IB crawler output would sit in
the new tables forever, fully "READY_FOR_RAG" per
scripts/report_policy_data_readiness.py, but genuinely unreachable by the
actual RAG pipeline. This script is the sync step that makes it reachable.

What it does
-------------
For every document_registry row with availability_status='AVAILABLE' and at
least one document_snapshots row (i.e. an actual downloaded file, not just a
catalog entry), OR availability_status='INLINE_TEXT_AVAILABLE' (a page whose
content already IS the document -- no LinkButton, no file at all; see
resolve_ib_product_details.py's _inline_text_entry docstring). The latter
skips the download-file path entirely: its metadata.inline_text goes
straight to policy_documents.parsed_text + policy_document_chunks via
_upsert_inline_text_document, since there's no PDF to run
parse_pdf_snapshots.py over:

  1. Resolve a product_db_id (insurance_products.id):
     - If the row's product_version_id has already been reconciled
       (scripts/reconcile_source_records.py) to a product_versions row, use
       that version's canonical_company_name/canonical_product_name/
       product_code to find or create the insurance_products row.
     - If there's no product_version_id (not yet reconciled) or no matching
       insurance_products row exists, a minimal one is created --
       `source` is set to 'tii' or 'ib_disclosure' (from document_registry.source),
       never silently left as the table's 'existing_crawl' default, so it's
       always possible to tell a company-crawled row from a bridged one.
  2. Insert (or refresh) a policy_documents row from the LATEST
     document_snapshots row for that document_registry_id.

Idempotency: keyed on (product_db_id, checksum), not (product_db_id,
pdf_url) -- verified live (see scripts/download_ib_documents.py) that IB's
resolved download URL is a one-time-use token, not stable, so two
downloads of byte-identical content can have two different pdf_urls. A
checksum match means "we've already synced this exact content" regardless
of what its pdf_url happened to be that time.

What it never does: delete any existing insurance_products/policy_documents
row, or touch a row this script didn't itself create/previously sync (no
existing table has a notion of "manually entered" policy_documents today --
customer-uploaded documents live in a completely separate table,
customer_policy_uploads -- but this script still only ever INSERTs new rows
or UPDATEs rows it created on an earlier run, matched by checksum, never a
blanket overwrite).

Usage:
    python scripts/sync_document_registry_to_policy_documents.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inventory_db import get_inventory_connection  # noqa: E402
from parse_pdf_snapshots import chunk_text  # noqa: E402


def _find_or_create_product(conn, document_registry_row: dict[str, Any]) -> tuple[int, bool]:
    """Returns (insurance_products.id, created)."""
    product_version_id = document_registry_row["product_version_id"]
    source_code = document_registry_row["source"] or "unknown"

    company_name = ""
    product_name = ""
    product_code = ""
    category = ""

    if product_version_id:
        version = conn.execute(
            "SELECT canonical_company_name, canonical_product_name, product_code, insurance_category "
            "FROM product_versions WHERE id = ?",
            (product_version_id,),
        ).fetchone()
        if version:
            company_name, product_name, product_code, category = version

    if not company_name or not product_name:
        # Not reconciled yet, or reconciled to a version missing these --
        # fall back to the source_product_records row this document came
        # from, via its source_record_id.
        source_record_id = document_registry_row["source_record_id"]
        if source_record_id:
            record = conn.execute(
                "SELECT company_name, product_name, product_code, insurance_category FROM source_product_records WHERE id = ?",
                (source_record_id,),
            ).fetchone()
            if record:
                company_name = company_name or record[0]
                product_name = product_name or record[1]
                product_code = product_code or record[2]
                category = category or record[3]

    company_name = company_name or "未知保險公司"
    # Store the company's short name (臺灣產物, not 臺灣產物保險股份有限公司)
    # when insurance_companies knows it -- that's what every other source
    # (company crawls, TII) uses, so the product list's company filter shows
    # one entry per company instead of two spellings.
    short = conn.execute(
        "SELECT short_name FROM insurance_companies WHERE name = ? OR short_name = ? LIMIT 1",
        (company_name, company_name),
    ).fetchone()
    if short:
        company_name = short[0]
    product_name = product_name or f"未命名商品（{source_code}）"

    # BUG FIXED HERE: this used to fall back to f"dr-{document_registry_row['id']}"
    # when there was no product_code/product_version_id -- keyed per
    # *document*, not per *product*, so a product with 3 unreconciled
    # documents (product_version_id still NULL, before
    # reconcile_source_records.py has run) got 3 separate insurance_products
    # rows instead of 1. source_record_id is the correct grouping key here:
    # every document_registry row for the same product shares the same
    # source_product_records row, reconciled or not. Falling back further to
    # the document_registry id only happens if source_record_id is somehow
    # NULL too (shouldn't happen given the schema, but better one extra
    # product row than a crash on a missing key).
    if product_code:
        product_id = product_code
    elif product_version_id:
        product_id = f"pv-{product_version_id}"
    elif document_registry_row["source_record_id"]:
        product_id = f"spr-{document_registry_row['source_record_id']}"
    else:
        product_id = f"dr-{document_registry_row['id']}"

    existing = conn.execute(
        "SELECT id FROM insurance_products WHERE product_id = ? AND company_name = ?",
        (product_id, company_name),
    ).fetchone()
    if existing:
        return existing[0], False

    cursor = conn.execute(
        """
        INSERT INTO insurance_products (
            product_id, company_name, product_name, category, status, source, metadata
        ) VALUES (?, ?, ?, ?, 'unknown', ?, ?)
        RETURNING id
        """,
        (
            product_id,
            company_name,
            product_name,
            category or "其他",
            source_code,
            json.dumps({"bridged_from": "document_registry", "product_version_id": product_version_id}, ensure_ascii=False),
        ),
    )
    return cursor.fetchone()[0], True


def _latest_snapshot(conn, document_registry_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT url, final_url, content_type, local_path, checksum, downloaded_at
        FROM document_snapshots
        WHERE document_registry_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (document_registry_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "url": row[0], "final_url": row[1], "content_type": row[2],
        "local_path": row[3], "checksum": row[4], "downloaded_at": row[5],
    }


# scripts/parse_pdf_snapshots.py only ever reads local_path with pdfplumber/
# pypdf -- it has no idea a .xls/.doc file exists, and pointing it at one via
# text_status='pending' would make it try to parse binary spreadsheet/Word
# content as a PDF (crash or garbage, not a clean skip). A synced non-PDF
# document is therefore marked 'downloaded_not_parsed' up front: it's
# genuinely on disk (documents_downloaded counts it), but
# report_policy_data_readiness.py must not report it as parsed, and
# parse_pdf_snapshots.py's own 'pending' query correctly never picks it up.
_PARSEABLE_EXTENSIONS = {".pdf"}


def _initial_text_status(local_path: str) -> str:
    suffix = Path(local_path).suffix.lower()
    return "pending" if suffix in _PARSEABLE_EXTENSIONS else "downloaded_not_parsed"


def _upsert_policy_document(
    conn, product_db_id: int, document_type: str, title: str, snapshot: dict[str, Any]
) -> tuple[int, bool]:
    checksum = snapshot["checksum"] or ""
    if checksum:
        existing = conn.execute(
            "SELECT id, pdf_url FROM policy_documents WHERE product_db_id = ? AND checksum = ?",
            (product_db_id, checksum),
        ).fetchone()
        if existing:
            return existing[0], False

    text_status = _initial_text_status(snapshot["local_path"] or "")

    # UNIQUE(product_db_id, pdf_url) still applies -- pdf_url here is a
    # one-time-use token per the module docstring, so a collision on it
    # specifically (as opposed to on checksum, handled above) would mean
    # the exact same transient URL was captured twice, which upsert-on-conflict
    # handles by refreshing rather than erroring.
    cursor = conn.execute(
        """
        INSERT INTO policy_documents (
            product_db_id, document_type, title, pdf_url, final_pdf_url,
            local_path, checksum, pdf_status, text_status, downloaded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ok', ?, ?)
        ON CONFLICT(product_db_id, pdf_url) DO UPDATE SET
            document_type = excluded.document_type,
            title = excluded.title,
            final_pdf_url = excluded.final_pdf_url,
            local_path = excluded.local_path,
            checksum = excluded.checksum,
            pdf_status = 'ok',
            downloaded_at = excluded.downloaded_at,
            updated_at = datetime('now')
        """,
        (
            product_db_id,
            document_type,
            title,
            snapshot["url"] or "",
            snapshot["final_url"] or "",
            snapshot["local_path"] or "",
            checksum,
            text_status,
            snapshot["downloaded_at"],
        ),
    )
    row = conn.execute(
        "SELECT id FROM policy_documents WHERE product_db_id = ? AND pdf_url = ?",
        (product_db_id, snapshot["url"] or ""),
    ).fetchone()
    return row[0], True


def _upsert_inline_text_document(
    conn, product_db_id: int, document_type: str, title: str, source_urn: str, inline_text: str
) -> tuple[int, bool]:
    """Sibling of _upsert_policy_document() for INLINE_TEXT_AVAILABLE rows
    (see resolve_ib_product_details.py's _inline_text_entry) -- there is no
    file to download for these, so instead of a document_snapshots row this
    reads straight from document_registry.metadata.inline_text, and since
    that text already IS the fully-extracted content (no PDF to run
    pdfplumber/pypdf over), it goes straight to text_status='parsed' with
    chunks built right here -- chunk_text() is scripts/parse_pdf_snapshots.py's
    own chunker, reused rather than reimplemented so both paths produce
    identically-shaped chunks for the RAG pipeline.

    Idempotency: keyed on (product_db_id, checksum) like the file-backed
    path, where checksum = sha256 of the inline text itself (there's no
    downloaded file to hash) -- and additionally on pdf_url = the
    deterministic `urn:ib-inline-text:...` key (stable, unlike a real
    document's transient DownLoad.aspx token), so a re-sync after the same
    inline text is seen again is a no-op rather than a duplicate row.
    """
    checksum = hashlib.sha256(inline_text.encode("utf-8")).hexdigest()
    existing = conn.execute(
        "SELECT id FROM policy_documents WHERE product_db_id = ? AND checksum = ?",
        (product_db_id, checksum),
    ).fetchone()
    if existing:
        return existing[0], False

    chunks = chunk_text(inline_text, size=1800, overlap=180)
    conn.execute(
        """
        INSERT INTO policy_documents (
            product_db_id, document_type, title, pdf_url, final_pdf_url,
            local_path, checksum, pdf_status, text_status, parsed_text, downloaded_at
        ) VALUES (?, ?, ?, ?, '', '', ?, 'inline_text', 'parsed', ?, datetime('now'))
        ON CONFLICT(product_db_id, pdf_url) DO UPDATE SET
            document_type = excluded.document_type,
            title = excluded.title,
            checksum = excluded.checksum,
            pdf_status = 'inline_text',
            text_status = 'parsed',
            parsed_text = excluded.parsed_text,
            downloaded_at = excluded.downloaded_at,
            updated_at = datetime('now')
        """,
        (product_db_id, document_type, title, source_urn, checksum, inline_text),
    )
    row = conn.execute(
        "SELECT id FROM policy_documents WHERE product_db_id = ? AND pdf_url = ?",
        (product_db_id, source_urn),
    ).fetchone()
    document_id = row[0]
    conn.execute("DELETE FROM policy_document_chunks WHERE document_id = ?", (document_id,))
    for index, chunk in enumerate(chunks):
        conn.execute(
            """
            INSERT INTO policy_document_chunks (document_id, product_db_id, chunk_index, text, token_estimate)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, product_db_id, index, chunk, max(1, len(chunk) // 3)),
        )
    return document_id, True


def run() -> dict[str, Any]:
    stats = {
        "candidates": 0,
        "products_created": 0,
        "products_reused": 0,
        "documents_synced": 0,
        "documents_unchanged": 0,
        "inline_text_synced": 0,
        "skipped_no_snapshot": 0,
        "skipped_empty_inline_text": 0,
        "errors": [],
    }

    with get_inventory_connection() as conn:
        rows = conn.execute(
            "SELECT id, product_version_id, source_record_id, source, document_type, title, availability_status, metadata "
            "FROM document_registry WHERE availability_status IN ('AVAILABLE', 'INLINE_TEXT_AVAILABLE')"
        ).fetchall()
        stats["candidates"] = len(rows)

        for row in rows:
            registry_row = {
                "id": row[0], "product_version_id": row[1], "source_record_id": row[2],
                "source": row[3], "document_type": row[4], "title": row[5],
            }
            availability_status = row[6]

            if availability_status == "INLINE_TEXT_AVAILABLE":
                try:
                    metadata = json.loads(row[7]) if row[7] else {}
                except json.JSONDecodeError:
                    metadata = {}
                inline_text = (metadata.get("inline_text") or "").strip()
                if not inline_text:
                    stats["skipped_empty_inline_text"] += 1
                    continue
                try:
                    product_db_id, product_created = _find_or_create_product(conn, registry_row)
                    stats["products_created" if product_created else "products_reused"] += 1
                    # _document_registry_entries() (resolve_ib_product_details.py)
                    # builds this row's url as the deterministic
                    # urn:ib-inline-text:... key -- reused here as
                    # policy_documents.pdf_url, see _upsert_inline_text_document.
                    source_urn = conn.execute(
                        "SELECT url FROM document_registry WHERE id = ?", (registry_row["id"],)
                    ).fetchone()[0]
                    _, doc_created = _upsert_inline_text_document(
                        conn, product_db_id, registry_row["document_type"], registry_row["title"], source_urn, inline_text
                    )
                    stats["inline_text_synced" if doc_created else "documents_unchanged"] += 1
                except Exception as exc:  # noqa: BLE001 -- one bad row shouldn't abort the whole sync
                    stats["errors"].append({"document_registry_id": registry_row["id"], "error": str(exc)[:240]})
                continue

            snapshot = _latest_snapshot(conn, registry_row["id"])
            if snapshot is None or not snapshot["local_path"]:
                stats["skipped_no_snapshot"] += 1
                continue

            try:
                product_db_id, product_created = _find_or_create_product(conn, registry_row)
                stats["products_created" if product_created else "products_reused"] += 1

                _, doc_created = _upsert_policy_document(
                    conn, product_db_id, registry_row["document_type"], registry_row["title"], snapshot
                )
                stats["documents_synced" if doc_created else "documents_unchanged"] += 1
            except Exception as exc:  # noqa: BLE001 -- one bad row shouldn't abort the whole sync
                stats["errors"].append({"document_registry_id": registry_row["id"], "error": str(exc)[:240]})

    return stats


def main() -> None:
    summary = run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
