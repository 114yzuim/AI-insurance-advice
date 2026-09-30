"""Repository helpers for the Phase-2 market-universe tables
(0002_market_universe.sql): inventory_sources, crawl_runs,
source_product_records, document_registry, etc.

This module is source-agnostic on purpose -- it takes a `source_code`
string (`"tii"`, `"ib_disclosure"`, `"company_site"`, ...) rather than
hardcoding TII-specific fields, so the same upsert path works once an IB
disclosure importer exists.

Nothing here touches insurance_products / policy_documents /
policy_document_chunks -- those stay exactly as the existing crawl/RAG
pipeline left them. Reconciling this layer against them is a later phase.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Any

# (code, name, authority_level, base_url, notes)
DEFAULT_SOURCES: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "tii",
        "財團法人保險事業發展中心 商品資料庫",
        "central_registry",
        "https://insprod.tii.org.tw",
        "Query/list forms are CAPTCHA-gated; see scripts/sources/tii/README.md. "
        "Per TII, coverage starts ~民國93年 (2004) -- products sold before that "
        "may not appear.",
    ),
    (
        "ib_disclosure",
        "保險業公開資訊觀測站",
        "regulatory_disclosure",
        "https://ins-info.ib.gov.tw",
        "Placeholder source row for the IB (保險業公開資訊觀測站) disclosure "
        "feed; no importer exists yet.",
    ),
    (
        "company_site",
        "保險公司官網（既有 adapter 爬取）",
        "primary",
        "",
        "Represents the existing scripts/adapters/*.py company-site crawl, "
        "for when it is reconciled into this layer.",
    ),
    (
        "reconciliation",
        "系統內部比對任務",
        "internal",
        "",
        "Not a data source -- a home for crawl_runs rows logged by "
        "scripts/reconcile_source_records.py, which reads across every real "
        "source rather than belonging to just one of them.",
    ),
)


def hash_payload(payload: Any) -> str:
    """Deterministic hash of a JSON-able payload (sorted keys, no whitespace).

    Two payloads that are equal as data hash the same regardless of key
    order, so this is safe to use as a "did anything change" check between
    two fetches of the same source record.

    Callers hashing a raw source payload for change-detection should pass it
    through stable_payload_for_hash() first -- see that function's docstring
    for why.
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Fields that change on every fetch/save even when the underlying product
# data hasn't -- a re-fetch timestamp, the path of whatever snapshot file
# this particular run happened to write to, etc. Hashing these in would make
# every re-import look like a content change even when nothing about the
# product itself moved.
_VOLATILE_PAYLOAD_KEYS = {
    "fetched_at",
    "source_html_path",
    "crawl_run_id",
    "imported_at",
    "downloaded_at",
    "snapshot_path",
    "snapshot_paths",  # plural: a multi-fetch record (e.g. IB's 5 detail pages) recording several
}


def stable_payload_for_hash(payload: Any) -> Any:
    """Drop volatile, non-business fields before hashing a source payload.

    Strips at the top level, plus one named exception one level down: a
    top-level "detail" key (added by
    update_source_product_record_from_detail() when a list-origin record
    gets backfilled from a DetailList.aspx fetch) is itself a small dict
    with its own fetched_at/source_html_path, stripped the same way. This is
    a deliberate, explicit special case -- not a general recursive strip,
    which could silently swallow a legitimately-named business field nested
    somewhere else. If another nested volatile field shows up in a future
    source, add it here by name rather than making this function recursive.
    """
    if not isinstance(payload, dict):
        return payload
    result = {k: v for k, v in payload.items() if k not in _VOLATILE_PAYLOAD_KEYS}
    if isinstance(result.get("detail"), dict):
        result["detail"] = {k: v for k, v in result["detail"].items() if k not in _VOLATILE_PAYLOAD_KEYS}
    return result


def ensure_default_sources(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert the known source rows, or refresh their reference fields if
    already present (these are our own maintained descriptions, e.g. base_url
    -- not user-editable data, so an existing row is safe to keep in sync
    rather than frozen at whatever it had on first insert).

    Returns {code: id} for all of them.
    """
    for code, name, authority_level, base_url, notes in DEFAULT_SOURCES:
        conn.execute(
            """
            INSERT INTO inventory_sources (code, name, authority_level, base_url, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                authority_level = excluded.authority_level,
                base_url = excluded.base_url,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (code, name, authority_level, base_url, notes),
        )
    rows = conn.execute("SELECT code, id FROM inventory_sources").fetchall()
    return {row[0]: row[1] for row in rows}


def _get_or_create_source_id(conn: sqlite3.Connection, source_code: str) -> int:
    """Look up a source's id, auto-registering an unknown code defensively.

    Callers are expected to have called ensure_default_sources() up front;
    this fallback just keeps an unrecognized-but-plausible source_code (e.g.
    a new one added to DEFAULT_SOURCES in a later change, or a one-off script
    run before this module is updated) from hard-failing the whole import.
    """
    row = conn.execute("SELECT id FROM inventory_sources WHERE code = ?", (source_code,)).fetchone()
    if row:
        return row[0]
    conn.execute(
        """
        INSERT INTO inventory_sources (code, name, authority_level, base_url, notes)
        VALUES (?, ?, 'secondary', '', 'auto-registered by inventory_repository')
        ON CONFLICT(code) DO NOTHING
        """,
        (source_code, source_code),
    )
    row = conn.execute("SELECT id FROM inventory_sources WHERE code = ?", (source_code,)).fetchone()
    return row[0]


def create_crawl_run(
    conn: sqlite3.Connection,
    source_code: str,
    run_type: str,
    metadata: dict | None = None,
) -> int:
    source_id = _get_or_create_source_id(conn, source_code)
    # RETURNING id + fetchone() instead of cursor.lastrowid: identical on
    # SQLite (3.35+, RETURNING has been available since 2021) and
    # PostgreSQL (which has no lastrowid at all) -- see backend/
    # pg_compat.py's module docstring for the full Postgres-portability
    # audit this pattern comes from. Every INSERT in this file that needs
    # the new row's id now does this instead of relying on lastrowid.
    cursor = conn.execute(
        """
        INSERT INTO crawl_runs (source_id, run_type, status, metadata)
        VALUES (?, ?, 'running', ?)
        RETURNING id
        """,
        (source_id, run_type, json.dumps(metadata or {}, ensure_ascii=False)),
    )
    return cursor.fetchone()[0]


def finish_crawl_run(
    conn: sqlite3.Connection,
    crawl_run_id: int,
    status: str,
    records_seen: int = 0,
    records_changed: int = 0,
    error: str = "",
) -> None:
    conn.execute(
        """
        UPDATE crawl_runs
        SET status = ?, records_seen = ?, records_changed = ?, error = ?, finished_at = datetime('now')
        WHERE id = ?
        """,
        (status, records_seen, records_changed, error, crawl_run_id),
    )


# Fields on source_product_records that upsert_source_product_record() will
# write/compare. Keys are column names; values are how to pull them out of
# the caller's `record` dict (defaulting to "").
_SOURCE_RECORD_TEXT_FIELDS = (
    "source_product_url",
    "company_name",
    "product_code",
    "product_name",
    "insurance_category",
    "insurance_type",
    "sale_start_date",
    "sale_end_date",
    "approval_date",
    "approval_number",
    "filing_number",
    "review_method",
)


def upsert_source_product_record(
    conn: sqlite3.Connection,
    source_code: str,
    record: dict[str, Any],
) -> tuple[int, bool]:
    """Insert or refresh one source_product_records row.

    `record` must have `source_product_id` and `raw_payload` (a JSON-able
    dict/list -- the full original record, kept verbatim); every field in
    _SOURCE_RECORD_TEXT_FIELDS is optional and defaults to "". `crawl_run_id`
    is optional.

    Returns (row_id, changed) where `changed` is True for a brand new row or
    one whose *stable* raw_payload hash differs from what's stored -- see
    stable_payload_for_hash() -- so a re-fetch that only moved fetched_at /
    source_html_path forward does not count as a change; a re-seen record
    only gets its last_seen_at touched in that case. raw_payload itself is
    still stored and updated in full either way.
    """
    source_product_id = record["source_product_id"]
    raw_payload = record.get("raw_payload", {})
    payload_hash = hash_payload(stable_payload_for_hash(raw_payload))
    source_id = _get_or_create_source_id(conn, source_code)
    crawl_run_id = record.get("crawl_run_id")
    values = {field: record.get(field) or "" for field in _SOURCE_RECORD_TEXT_FIELDS}

    existing = conn.execute(
        "SELECT id, payload_hash FROM source_product_records WHERE source_id = ? AND source_product_id = ?",
        (source_id, source_product_id),
    ).fetchone()

    if existing is None:
        cursor = conn.execute(
            f"""
            INSERT INTO source_product_records (
                source_id, crawl_run_id, source_product_id, raw_payload, payload_hash,
                {', '.join(_SOURCE_RECORD_TEXT_FIELDS)}
            ) VALUES (
                ?, ?, ?, ?, ?,
                {', '.join('?' for _ in _SOURCE_RECORD_TEXT_FIELDS)}
            )
            RETURNING id
            """,
            (
                source_id,
                crawl_run_id,
                source_product_id,
                json.dumps(raw_payload, ensure_ascii=False),
                payload_hash,
                *(values[field] for field in _SOURCE_RECORD_TEXT_FIELDS),
            ),
        )
        return cursor.fetchone()[0], True

    row_id, previous_hash = existing
    changed = previous_hash != payload_hash
    if changed:
        conn.execute(
            f"""
            UPDATE source_product_records
            SET crawl_run_id = ?, raw_payload = ?, payload_hash = ?,
                {', '.join(f'{field} = ?' for field in _SOURCE_RECORD_TEXT_FIELDS)},
                last_seen_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                crawl_run_id,
                json.dumps(raw_payload, ensure_ascii=False),
                payload_hash,
                *(values[field] for field in _SOURCE_RECORD_TEXT_FIELDS),
                row_id,
            ),
        )
    else:
        # Business content is unchanged, but still refresh raw_payload (it
        # carries this fetch's fetched_at/source_html_path as evidence of
        # when we last confirmed it) and crawl_run_id. updated_at is left
        # alone -- it means "business content last changed", not "last seen".
        conn.execute(
            """
            UPDATE source_product_records
            SET crawl_run_id = ?, raw_payload = ?, last_seen_at = datetime('now')
            WHERE id = ?
            """,
            (crawl_run_id, json.dumps(raw_payload, ensure_ascii=False), row_id),
        )
    return row_id, changed


_DOCUMENT_REGISTRY_FIELDS = ("document_type", "title", "final_url", "source_document_id")


def upsert_document_registry(
    conn: sqlite3.Connection,
    source_record_id: int,
    document: dict[str, Any],
) -> tuple[int, bool]:
    """Insert or refresh one document_registry row, keyed on (source_record_id, url).

    `document` must have `url`; `source`, `document_type`, `title`,
    `source_document_id`, `final_url`, `metadata` and `availability_status`
    are optional. `product_version_id` is left NULL -- Phase 3's
    reconciliation step fills that in once a source record is matched to a
    canonical product version.

    `availability_status`, when given, is written on INSERT (instead of
    falling back to the schema's 'UNKNOWN' default) and kept in sync on
    UPDATE -- used by resolve_ib_product_details.py to mark an inline-text
    "document" (page content with no downloadable file at all, see its
    module docstring) as INLINE_TEXT_AVAILABLE immediately, without waiting
    for scripts/download_ib_documents.py to ever touch it (there's nothing
    to postback/download for these). Omitted (None), it's left alone on an
    UPDATE and defaults to the schema's 'UNKNOWN' on INSERT, same as before
    this parameter existed.
    """
    url = document["url"]
    source = document.get("source") or ""
    metadata = document.get("metadata") or {}
    availability_status = document.get("availability_status")
    values = {field: document.get(field) or "" for field in _DOCUMENT_REGISTRY_FIELDS}

    existing = conn.execute(
        "SELECT id, document_type, title, final_url, source_document_id, metadata, availability_status "
        "FROM document_registry WHERE source_record_id = ? AND url = ?",
        (source_record_id, url),
    ).fetchone()

    if existing is None:
        cursor = conn.execute(
            """
            INSERT INTO document_registry (
                source_record_id, source, document_type, title, url, final_url,
                source_document_id, metadata, availability_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 'UNKNOWN'))
            RETURNING id
            """,
            (
                source_record_id,
                source,
                values["document_type"] or "OTHER",
                values["title"],
                url,
                values["final_url"],
                values["source_document_id"],
                json.dumps(metadata, ensure_ascii=False),
                availability_status,
            ),
        )
        return cursor.fetchone()[0], True

    row_id, prev_type, prev_title, prev_final_url, prev_doc_id, prev_metadata, prev_availability = existing
    new_metadata_json = json.dumps(metadata, ensure_ascii=False)
    changed = (
        prev_type != (values["document_type"] or "OTHER")
        or prev_title != values["title"]
        or prev_final_url != values["final_url"]
        or prev_doc_id != values["source_document_id"]
        or prev_metadata != new_metadata_json
        or (availability_status is not None and prev_availability != availability_status)
    )
    if changed:
        conn.execute(
            """
            UPDATE document_registry
            SET source = ?, document_type = ?, title = ?, final_url = ?,
                source_document_id = ?, metadata = ?,
                availability_status = COALESCE(?, availability_status),
                last_seen_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                source,
                values["document_type"] or "OTHER",
                values["title"],
                values["final_url"],
                values["source_document_id"],
                new_metadata_json,
                availability_status,
                row_id,
            ),
        )
    else:
        conn.execute(
            "UPDATE document_registry SET last_seen_at = datetime('now') WHERE id = ?",
            (row_id,),
        )
    return row_id, changed


# ---------------------------------------------------------------------------
# Phase 3: source_product_records -> product_families / product_versions
#
# Matching here is deliberately rule-based only (string normalization), never
# LLM/embedding-based -- see scripts/reconcile_source_records.py's module
# docstring for the reasoning. With only TII populated so far, each source
# record maps 1:1 to its own product_version; the payoff of this layer
# (multiple sources collapsing into one family/version) starts once a second
# source's records exist for the same product.
# ---------------------------------------------------------------------------

# Company-name suffix/branch tokens stripped before matching, longest first
# so e.g. "產物保險股份有限公司" is removed as one unit rather than leaving a
# stray "產物" behind after a shorter suffix matches first.
_COMPANY_SUFFIX_TOKENS = sorted(
    [
        "人壽保險股份有限公司",
        "產物保險股份有限公司",
        "產物保險股份有限公司台灣分公司",
        "人壽保險股份有限公司台灣分公司",
        "保險股份有限公司台灣分公司",
        "保險股份有限公司",
        "股份有限公司台灣分公司",
        "股份有限公司",
        "有限公司",
        "台灣分公司",
        "分公司",
    ],
    key=len,
    reverse=True,
)
_COMPANY_SUFFIX_RE = re.compile("|".join(re.escape(token) for token in _COMPANY_SUFFIX_TOKENS))


def normalize_company_name(name: str) -> str:
    """Strip whitespace and common corporate-form/branch suffixes.

    Not meant to fully canonicalize a legal entity name (jurisdiction
    prefixes like "英屬百慕達商" or "美商" are left in place on purpose --
    dropping those could quietly merge two different foreign branches). Just
    enough to stop "南山人壽保險股份有限公司" and "南山人壽" from being treated
    as different companies.
    """
    text = unicodedata.normalize("NFKC", name or "")
    text = _COMPANY_SUFFIX_RE.sub("", text)
    return re.sub(r"\s+", "", text).strip()


def normalize_product_name(name: str) -> str:
    """Full-width/half-width + whitespace normalization only.

    No fuzzy matching, no stopword removal -- two product names that differ
    by more than that are left as different products rather than guessed at.
    """
    text = unicodedata.normalize("NFKC", name or "")
    return re.sub(r"\s+", "", text).strip()


def normalized_key_for(company_name: str, product_name: str) -> str:
    return f"{normalize_company_name(company_name)}::{normalize_product_name(product_name)}"


def upsert_product_family(
    conn: sqlite3.Connection,
    company_name: str,
    product_name: str,
) -> tuple[int, bool]:
    """Insert or fetch the product_families row for (company_name, product_name).

    The canonical_company_name/canonical_product_name are set once, from
    whichever record first creates the family, and left alone after that --
    picking a "best" display name across sources is a judgment call this
    rule-based pass doesn't try to make. Returns (family_id, created).
    """
    key = normalized_key_for(company_name, product_name)
    existing = conn.execute(
        "SELECT id FROM product_families WHERE normalized_key = ?", (key,)
    ).fetchone()
    if existing:
        return existing[0], False
    cursor = conn.execute(
        """
        INSERT INTO product_families (canonical_company_name, canonical_product_name, normalized_key)
        VALUES (?, ?, ?)
        RETURNING id
        """,
        (company_name, product_name, key),
    )
    return cursor.fetchone()[0], True


_PRODUCT_VERSION_FIELDS = (
    "canonical_company_name",
    "canonical_product_name",
    "product_code",
    "insurance_category",
    "insurance_type",
    "sale_start_date",
    "sale_end_date",
    "approval_date",
    "approval_number",
    "filing_number",
    "review_method",
    "version_label",
)


def upsert_product_version(
    conn: sqlite3.Connection,
    source_record_id: int,
    product_family_id: int,
    fields: dict[str, Any],
    match_confidence: float = 1.0,
) -> tuple[int, str]:
    """Insert or refresh the product_versions row keyed on primary_source_record_id.

    One source_product_records row maps to exactly one product_versions row
    for now (see module-level note above) -- `source_record_id` is therefore
    the de-dup key, the same role `(source_id, source_product_id)` plays for
    source_product_records itself. `fields` supplies any of
    _PRODUCT_VERSION_FIELDS; missing ones default to "".

    canonical_status is deliberately left untouched here (defaults to
    'NEEDS_REVIEW' from the schema on first insert, and is not overwritten
    on update) -- assigning it meaningfully requires the cross-source
    evidence Phase 3 doesn't have yet with only one populated source. See
    scripts/reconcile_source_records.py.

    Returns (row_id, status) where status is "created", "updated" (some
    field actually differs from what's stored), or "unchanged" -- a re-run
    over unchanged data is a no-op write; updated_at is not bumped just
    because the script ran again.
    """
    values = {field: fields.get(field) or "" for field in _PRODUCT_VERSION_FIELDS}
    existing = conn.execute(
        f"SELECT id, product_family_id, match_confidence, {', '.join(_PRODUCT_VERSION_FIELDS)} "
        "FROM product_versions WHERE primary_source_record_id = ?",
        (source_record_id,),
    ).fetchone()

    if existing is None:
        cursor = conn.execute(
            f"""
            INSERT INTO product_versions (
                product_family_id, primary_source_record_id, match_confidence,
                {', '.join(_PRODUCT_VERSION_FIELDS)}
            ) VALUES (
                ?, ?, ?,
                {', '.join('?' for _ in _PRODUCT_VERSION_FIELDS)}
            )
            RETURNING id
            """,
            (
                product_family_id,
                source_record_id,
                match_confidence,
                *(values[field] for field in _PRODUCT_VERSION_FIELDS),
            ),
        )
        return cursor.fetchone()[0], "created"

    row_id, prev_family_id, prev_confidence, *prev_values = existing
    changed = (prev_family_id, prev_confidence, *prev_values) != (
        product_family_id,
        match_confidence,
        *(values[field] for field in _PRODUCT_VERSION_FIELDS),
    )
    if changed:
        conn.execute(
            f"""
            UPDATE product_versions
            SET product_family_id = ?, match_confidence = ?,
                {', '.join(f'{field} = ?' for field in _PRODUCT_VERSION_FIELDS)},
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                product_family_id,
                match_confidence,
                *(values[field] for field in _PRODUCT_VERSION_FIELDS),
                row_id,
            ),
        )
    return row_id, "updated" if changed else "unchanged"


def link_documents_to_product_version(
    conn: sqlite3.Connection,
    source_record_id: int,
    product_version_id: int,
) -> int:
    """Point every document_registry row for this source record at its
    product_version, now that one exists. Returns the number of rows touched.
    """
    cursor = conn.execute(
        "UPDATE document_registry SET product_version_id = ?, updated_at = datetime('now') "
        "WHERE source_record_id = ? AND (product_version_id IS NULL OR product_version_id != ?)",
        (product_version_id, source_record_id, product_version_id),
    )
    return cursor.rowcount


def count_distinct_sources_in_family(conn: sqlite3.Connection, product_family_id: int) -> int:
    """How many distinct inventory_sources feed into this family's versions.

    Used to decide whether a *_ONLY-style reconciliation finding is even
    meaningful yet: with only one source populated (today: just TII), every
    family would otherwise get a same "TII_ONLY" finding, which is noise, not
    information -- it just restates "we only have one source running". See
    scripts/reconcile_source_records.py.
    """
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT spr.source_id)
        FROM product_versions pv
        JOIN source_product_records spr ON spr.id = pv.primary_source_record_id
        WHERE pv.product_family_id = ?
        """,
        (product_family_id,),
    ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Phase 2.6: backfilling a list-origin source_product_records row (empty
# company_name etc.) with a DetailList.aspx parse -- see
# scripts/resolve_tii_details.py.
# ---------------------------------------------------------------------------


def update_source_product_record_from_detail(
    conn: sqlite3.Connection,
    source_record_id: int,
    parsed_record: dict[str, Any],
) -> bool:
    """Merge a DetailList.aspx parse result into an existing source_product_records row.

    Meant for a row that originally came from ResultQueryAll.aspx (so it
    already has source_product_id/detail_url but empty company_name/
    product_code/etc.) -- see scripts/resolve_tii_details.py.

    Evidence handling: raw_payload's existing top-level content (the
    original list-page record) is left completely untouched; `parsed_record`
    is stored verbatim under a new top-level "detail" key, added or replaced
    on each call. Nothing already in raw_payload is ever overwritten, only
    added to -- so a bad detail parse can always be re-inspected against
    exactly what the earlier list-page ingest produced.

    Column handling: every field in _SOURCE_RECORD_TEXT_FIELDS is updated
    from `parsed_record` only where the existing column is currently blank
    -- a detail fetch fills gaps, it never overwrites a value the list page
    (or an earlier detail fetch) already established.

    Change detection uses stable_payload_for_hash() the same way
    upsert_source_product_record() does -- see that function's docstring for
    how it handles this function's "detail" sub-key specifically -- so a
    detail_status/fetched_at/source_html_path difference between two
    fetches of an unchanged page does not register as a change.

    Returns True if anything about the stored row actually changed.
    """
    row = conn.execute(
        "SELECT raw_payload, payload_hash, " + ", ".join(_SOURCE_RECORD_TEXT_FIELDS) + " "
        "FROM source_product_records WHERE id = ?",
        (source_record_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no source_product_records row with id={source_record_id}")

    raw_payload_json, previous_hash, *existing_field_values = row
    try:
        raw_payload = json.loads(raw_payload_json) if raw_payload_json else {}
    except json.JSONDecodeError:
        raw_payload = {}

    existing = dict(zip(_SOURCE_RECORD_TEXT_FIELDS, existing_field_values))
    new_values = dict(existing)
    for field in _SOURCE_RECORD_TEXT_FIELDS:
        if existing[field]:
            continue  # never overwrite a value we already have
        detail_value = (parsed_record.get(field) or "").strip()
        if detail_value:
            new_values[field] = detail_value

    merged_raw_payload = dict(raw_payload)
    merged_raw_payload["detail"] = parsed_record

    new_payload_hash = hash_payload(stable_payload_for_hash(merged_raw_payload))
    changed = new_payload_hash != previous_hash or new_values != existing

    if changed:
        conn.execute(
            f"""
            UPDATE source_product_records
            SET raw_payload = ?, payload_hash = ?,
                {', '.join(f'{field} = ?' for field in _SOURCE_RECORD_TEXT_FIELDS)},
                last_seen_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                json.dumps(merged_raw_payload, ensure_ascii=False),
                new_payload_hash,
                *(new_values[field] for field in _SOURCE_RECORD_TEXT_FIELDS),
                source_record_id,
            ),
        )
    else:
        conn.execute(
            "UPDATE source_product_records SET raw_payload = ?, last_seen_at = datetime('now') WHERE id = ?",
            (json.dumps(merged_raw_payload, ensure_ascii=False), source_record_id),
        )
    return changed


# ---------------------------------------------------------------------------
# Document download -- document_snapshots + document_registry status.
# ---------------------------------------------------------------------------


def upsert_document_snapshot(
    conn: sqlite3.Connection,
    document_registry_id: int,
    snapshot: dict[str, Any],
) -> tuple[int, bool]:
    """Insert a document_snapshots row, or return the existing one if a
    snapshot with this exact (document_registry_id, checksum) already
    exists -- see 0003_document_snapshots_unique.sql. A re-download that
    produced byte-identical content is a no-op, not a new row.

    `snapshot` expects: url, final_url, content_type, local_path, checksum,
    file_size, parser_status (defaults to "pending"), and optionally
    object_store_uri/object_store_key (see 0004_object_storage_refs.sql --
    nullable, populated only by callers that also wrote the bytes to
    scripts/object_storage.py; omitted entirely for callers that don't).

    Returns (row_id, created) -- created=False means an existing snapshot
    with this checksum was found and reused untouched.
    """
    checksum = snapshot.get("checksum") or ""
    if checksum:
        existing = conn.execute(
            "SELECT id, object_store_uri FROM document_snapshots WHERE document_registry_id = ? AND checksum = ?",
            (document_registry_id, checksum),
        ).fetchone()
        if existing:
            existing_id, existing_object_store_uri = existing
            # Backfill-on-touch: this run already re-wrote these same bytes
            # to object storage (content-addressed, so that write was itself
            # a no-op if the object already existed -- see
            # object_storage.FileObjectStore.put_bytes) -- if the existing
            # row predates that wiring and has no object_store_uri yet,
            # record it now rather than silently discarding a ref this run
            # already has in hand. Never overwrites an existing non-empty
            # value (a NEW ref here from a differently-configured backend
            # shouldn't replace a working one from before).
            new_object_store_uri = snapshot.get("object_store_uri") or ""
            if new_object_store_uri and not existing_object_store_uri:
                conn.execute(
                    "UPDATE document_snapshots SET object_store_uri = ?, object_store_key = ? WHERE id = ?",
                    (new_object_store_uri, snapshot.get("object_store_key") or "", existing_id),
                )
            return existing_id, False

    cursor = conn.execute(
        """
        INSERT INTO document_snapshots (
            document_registry_id, url, final_url, content_type, local_path,
            checksum, file_size, downloaded_at, parser_status,
            object_store_uri, object_store_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
        RETURNING id
        """,
        (
            document_registry_id,
            snapshot.get("url") or "",
            snapshot.get("final_url") or "",
            snapshot.get("content_type") or "",
            snapshot.get("local_path") or "",
            checksum,
            snapshot.get("file_size") or 0,
            snapshot.get("parser_status") or "pending",
            snapshot.get("object_store_uri") or "",
            snapshot.get("object_store_key") or "",
        ),
    )
    return cursor.fetchone()[0], True


def update_document_registry_status(
    conn: sqlite3.Connection,
    document_registry_id: int,
    *,
    availability_status: str,
    final_url: str | None = None,
) -> None:
    """Set document_registry.availability_status (Phase 4 vocabulary --
    AVAILABLE/BROKEN_LINK/... ) after a download attempt. final_url is only
    written when given (a failed attempt that never resolved a real URL
    shouldn't blank out a previously-known one).
    """
    if final_url is not None:
        conn.execute(
            "UPDATE document_registry SET availability_status = ?, final_url = ?, updated_at = datetime('now') WHERE id = ?",
            (availability_status, final_url, document_registry_id),
        )
    else:
        conn.execute(
            "UPDATE document_registry SET availability_status = ?, updated_at = datetime('now') WHERE id = ?",
            (availability_status, document_registry_id),
        )


def record_document_download_error(
    conn: sqlite3.Connection,
    document_registry_id: int,
    evidence: dict,
    classification: dict,
    retested: bool = False,
) -> None:
    """Merge a download-failure's evidence + classification into
    document_registry.metadata under the "download_error" key, without
    disturbing whatever else already lives in that JSON blob (e.g.
    resolve_ib_product_details.py's function_number/note -- see its module
    docstring). Overwrites any previous "download_error" from an earlier
    attempt on the same row: only the latest attempt's evidence matters for
    scripts/analyze_ib_download_failures.py.
    """
    row = conn.execute("SELECT metadata FROM document_registry WHERE id = ?", (document_registry_id,)).fetchone()
    try:
        metadata = json.loads(row[0]) if row and row[0] else {}
    except json.JSONDecodeError:
        metadata = {}
    metadata["download_error"] = {
        **evidence,
        "category": classification["category"],
        "matched_pattern": classification.get("matched_pattern"),
        "reasoning": classification.get("reasoning"),
        "retested": retested,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    conn.execute(
        "UPDATE document_registry SET metadata = ?, updated_at = datetime('now') WHERE id = ?",
        (json.dumps(metadata, ensure_ascii=False), document_registry_id),
    )
