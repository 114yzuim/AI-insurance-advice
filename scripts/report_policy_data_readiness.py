"""Report how much of what's already been crawled is actually usable yet.

Reads source_product_records + document_registry (public products, staged
by the TII/IB crawlers -- Phases 2.5-2.9) and customer_policies +
customer_policy_coverages (customer-held policies, the pre-existing
health-check feature), runs everything through
scripts/policy_data_contract.py's validate_*/classify_*_readiness, and
reports counts. This is the "did all that crawling actually produce
something RAG/health-check/claim-prep can use" check the Policy Data
Contract exists to make answerable, instead of just trusting that a nonzero
row count in source_product_records means something useful is there.

Scope note: company adapters (scripts/adapters/*.py, which write into
insurance_products / policy_documents directly, not into
source_product_records) and the live OCR/policy-extraction pipeline
(backend/services/policy_extraction_service.py, which writes
customer_policies via a different code path with its own field names --
life_coverage/medical_daily/accident_coverage/cancer_coverage/
disability_monthly, not this contract's coverages dict) are NOT converted
through policy_data_contract.py by this script. Wiring those in is
additional, separate work this task didn't include touching live backend
request-handling code for -- see scripts/policy_data_contract.py's own
docstring for the converters that already exist (from_tii_source_record,
from_ib_source_record) and would need company-adapter / OCR-service
counterparts.

Usage:
    python scripts/report_policy_data_readiness.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from analyze_ib_download_failures import build_analysis  # noqa: E402
from inventory_db import get_inventory_connection  # noqa: E402
from policy_data_contract import (  # noqa: E402
    ClaimInfoRecord,
    CustomerPolicyRecord,
    DocumentType,
    ReadinessLevel,
    classify_customer_policy_readiness,
    classify_public_product_readiness,
    from_ib_source_record,
    from_tii_source_record,
    validate_customer_policy_record,
)

_CONVERTERS = {
    "tii": from_tii_source_record,
    "ib_disclosure": from_ib_source_record,
}

# See scripts/sources/ib_disclosure/failure_classifier.py's module docstring
# for the reasoning behind each category. "inline_text" is deliberately
# excluded from both buckets -- it isn't a real download failure, it's a
# LinkButton that was never a file in the first place.
_RECOVERABLE_CATEGORIES = {"event_target_error", "session_expired", "server_error", "waf_blocked"}
_SOURCE_BROKEN_CATEGORIES = {"source_not_found", "waf_false_positive"}


def _public_product_report(conn) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT spr.id, s.code, spr.raw_payload
        FROM source_product_records spr
        JOIN inventory_sources s ON s.id = spr.source_id
        """
    ).fetchall()

    stats = {
        "public_products_total": 0,
        "by_readiness": {level.value: 0 for level in ReadinessLevel},
        "ready_for_rag": 0,
        "missing_company_name": 0,
        "missing_policy_terms": 0,
        "unconverted_sources": {},  # source codes with no known converter, and how many rows
    }

    doc_rows = conn.execute("SELECT source_record_id, document_type FROM document_registry").fetchall()
    docs_by_record: dict[int, list[str]] = {}
    for record_id, document_type in doc_rows:
        docs_by_record.setdefault(record_id, []).append(document_type)

    for record_id, source_code, raw_payload_json in rows:
        converter = _CONVERTERS.get(source_code)
        if converter is None:
            stats["unconverted_sources"][source_code] = stats["unconverted_sources"].get(source_code, 0) + 1
            continue
        try:
            payload = json.loads(raw_payload_json) if raw_payload_json else {}
        except json.JSONDecodeError:
            continue

        product, documents = converter(payload)
        document_types = docs_by_record.get(record_id, [])
        # document_registry (already normalized at write time, and the
        # target of Phase 3 reconciliation) is the authoritative document
        # list once a record has been through resolve_*_details.py; fall
        # back to whatever the converter itself found in raw_payload for a
        # record that hasn't been reconciled yet.
        if document_types:
            has_policy_terms = DocumentType.POLICY_TERMS.value in document_types
        else:
            has_policy_terms = any(d.document_type == DocumentType.POLICY_TERMS.value for d in documents)

        readiness = _classify_with_policy_terms_flag(product, has_policy_terms)

        stats["public_products_total"] += 1
        stats["by_readiness"][readiness] += 1
        if readiness == ReadinessLevel.READY_FOR_RAG.value:
            stats["ready_for_rag"] += 1
        if not (product.company_name or "").strip():
            stats["missing_company_name"] += 1
        if not has_policy_terms:
            stats["missing_policy_terms"] += 1

    stats["documents_downloaded"] = conn.execute(
        "SELECT COUNT(DISTINCT document_registry_id) FROM document_snapshots"
    ).fetchone()[0]

    # "Parsed" reflects policy_documents.text_status, not
    # document_snapshots.parser_status -- nothing in this pipeline ever
    # writes that column; scripts/parse_pdf_snapshots.py and
    # scripts/parse_document_snapshots.py (the parsers that exist) read and
    # write policy_documents.text_status exclusively, via
    # scripts/sync_document_registry_to_policy_documents.py's bridge.
    # Matched by the concrete download URL captured for this document.
    # document_snapshots has no FK to policy_documents.
    #
    # BUG FIXED HERE (found live 2026-09-14, verified against 253/365 real
    # document_snapshots rows): checksum is NOT unique to one document --
    # the same content (e.g. a generic "短期費率不適用" boilerplate notice)
    # legitimately backs many unrelated products, each with its own
    # policy_documents row sharing that checksum (this is deliberate,
    # documented reuse -- see parse_pdf_snapshots.py's get_cached_parse). A
    # plain `LEFT JOIN ... ON pd.checksum = ds.checksum` therefore fans out:
    # one document_snapshots row can match several policy_documents rows
    # with DIFFERENT text_status values, and the old GROUP BY counted that
    # single document_registry_id into EVERY status bucket it fanned out
    # into -- so a document already 'parsed' via one product's copy could
    # never be seen leaving 'pending' when a DIFFERENT copy got parsed
    # later, silently misstating progress. Checksum AND local_path both
    # over-count when the same physical content is reused by multiple
    # products. IB postback downloads can produce the same content under many
    # product-specific one-time URLs, so the concrete final URL recorded
    # during the download is the one-to-one bridge to the synced
    # policy_documents row. The defensive "best status per
    # document_registry_id" collapse remains only for duplicate snapshot rows
    # of the same registry document.
    _STATUS_PRIORITY = {
        "parsed": 0,
        "downloaded_not_parsed": 1,
        "pending": 2,
        "scanned_pdf": 3,
        "parse_failed": 4,
        "parser_unavailable": 5,
        "unsupported_legacy_format": 6,
        "not_synced_to_policy_documents": 7,
    }
    _UNKNOWN_STATUS_PRIORITY = 99  # any future text_status value not yet listed above sorts last, not crashes
    per_document_status_rows = conn.execute(
        """
        SELECT ds.document_registry_id, COALESCE(pd.text_status, 'not_synced_to_policy_documents')
        FROM document_snapshots ds
        LEFT JOIN policy_documents pd
          ON (
            (pd.final_pdf_url = ds.final_url AND ds.final_url != '')
            OR (pd.pdf_url = ds.url AND ds.url != '')
          )
        """
    ).fetchall()
    best_status_by_document: dict[int, str] = {}
    for document_registry_id, status in per_document_status_rows:
        current = best_status_by_document.get(document_registry_id)
        if current is None or _STATUS_PRIORITY.get(status, _UNKNOWN_STATUS_PRIORITY) < _STATUS_PRIORITY.get(
            current, _UNKNOWN_STATUS_PRIORITY
        ):
            best_status_by_document[document_registry_id] = status
    documents_by_text_status: dict[str, int] = {}
    for status in best_status_by_document.values():
        documents_by_text_status[status] = documents_by_text_status.get(status, 0) + 1
    stats["documents_by_text_status"] = documents_by_text_status
    stats["documents_parsed"] = documents_by_text_status.get("parsed", 0)
    # "downloaded_not_parsed" now specifically means "no parser has been
    # attempted on this yet at all" (see scripts/parse_document_snapshots.py's
    # module docstring) -- parser_unavailable/unsupported_legacy_format are
    # reported as their own buckets rather than folded back in here, so this
    # number reflects genuine backlog, not "backlog plus every legacy format
    # we've already looked at and know we can't parse".
    stats["documents_downloaded_not_parsed"] = documents_by_text_status.get("downloaded_not_parsed", 0)
    stats["documents_parse_failed"] = documents_by_text_status.get("parse_failed", 0) + documents_by_text_status.get(
        "scanned_pdf", 0
    )
    stats["documents_parser_unavailable"] = documents_by_text_status.get("parser_unavailable", 0)
    stats["documents_unsupported_legacy_format"] = documents_by_text_status.get("unsupported_legacy_format", 0)

    # Download-failure classification (currently IB-only -- TII documents
    # don't go through the postback/DownLoad.aspx flow this classifies, see
    # scripts/sources/ib_disclosure/failure_classifier.py). Never counts a
    # broken/unavailable document as available just to make this number
    # look better -- these are read straight from document_registry.
    failure_analysis = build_analysis(conn)
    stats["documents_broken_by_type"] = failure_analysis["by_document_type"]
    stats["download_failure_reasons"] = failure_analysis["by_category"]
    stats["recoverable_failures"] = sum(
        count for category, count in failure_analysis["by_category"].items() if category in _RECOVERABLE_CATEGORIES
    )
    stats["source_broken_failures"] = sum(
        count for category, count in failure_analysis["by_category"].items() if category in _SOURCE_BROKEN_CATEGORIES
    )
    stats["waf_blocked_failures"] = failure_analysis["by_category"].get("waf_blocked", 0)
    stats["unclassified_legacy_failures"] = failure_analysis["by_category"].get("unclassified_legacy", 0)
    stats["download_failures_needing_review"] = failure_analysis["failed_total"] - (
        stats["recoverable_failures"] + stats["source_broken_failures"]
    )

    # download_success_rate is scoped to actual LinkButton download attempts
    # (documents_downloaded vs. every BROKEN_LINK/NOT_LISTED row) -- it
    # deliberately excludes INLINE_TEXT_AVAILABLE rows below, since those
    # never went through a download attempt at all (nothing to succeed or
    # fail at; see resolve_ib_product_details.py's _inline_text_entry).
    download_attempts = stats["documents_downloaded"] + failure_analysis["failed_total"]
    stats["download_success_rate"] = (
        round(stats["documents_downloaded"] / download_attempts, 4) if download_attempts else None
    )

    # Inline-text documents (resolve_ib_product_details.py's
    # _inline_text_entry) are a distinct third shape of "document" from
    # here on -- never downloaded, never a failure, content already
    # extracted. Counted separately so they're neither hidden inside
    # documents_downloaded (they were never downloaded) nor miscounted as a
    # download_failure_reasons bucket (they were never attempted).
    stats["inline_text_available"] = conn.execute(
        "SELECT COUNT(*) FROM document_registry WHERE source = 'ib_disclosure' AND availability_status = 'INLINE_TEXT_AVAILABLE'"
    ).fetchone()[0]

    # scripts/legacy_office_parser.py coverage -- .doc/.xls specifically,
    # since those are this phase's actual target (see that module's
    # docstring). Never counts parser_unavailable as parsed.
    legacy_office_rows = conn.execute(
        "SELECT text_status, COUNT(*) FROM policy_documents "
        "WHERE LOWER(local_path) LIKE '%.doc' OR LOWER(local_path) LIKE '%.xls' "
        "GROUP BY text_status"
    ).fetchall()
    legacy_office_by_status = {status: count for status, count in legacy_office_rows}
    stats["legacy_office_total"] = sum(legacy_office_by_status.values())
    stats["legacy_office_parsed"] = legacy_office_by_status.get("parsed", 0)
    stats["legacy_office_parser_unavailable"] = legacy_office_by_status.get("parser_unavailable", 0)
    stats["legacy_office_by_status"] = legacy_office_by_status

    parsed_by_type_rows = conn.execute(
        "SELECT document_type, COUNT(*) FROM policy_documents WHERE text_status = 'parsed' GROUP BY document_type"
    ).fetchall()
    stats["parsed_by_document_type"] = {doc_type: count for doc_type, count in parsed_by_type_rows}

    # scripts/object_storage.py (Task 3) -- populated by
    # scripts/download_ib_documents.py's object-storage write (Task 5).
    # object_store_uri is '' (the schema default, see
    # 0004_object_storage_refs.sql) for every row from before that wiring
    # existed and for any run started with --no-object-store, so this is a
    # coverage count, not a guarantee every download has one.
    object_store_row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM document_snapshots WHERE object_store_uri != ''"
    ).fetchone()
    stats["object_store_documents"] = object_store_row[0]
    stats["object_store_bytes"] = object_store_row[1]

    # parsed_by_parser is a proxy keyed on local_path's extension, not a
    # literally-recorded parser name -- policy_documents has no column for
    # which parser touched a row (scripts/parse_pdf_snapshots.py and
    # scripts/parse_document_snapshots.py both only ever write text_status/
    # parsed_text). Extension is a reliable enough stand-in given
    # document_parser_service.py's dispatch is itself purely
    # extension-based (see its parse_document()).
    parsed_ext_rows = conn.execute(
        "SELECT LOWER(local_path), 1 FROM policy_documents WHERE text_status = 'parsed'"
    ).fetchall()
    parsed_by_parser: dict[str, int] = {}
    for local_path, _ in parsed_ext_rows:
        suffix = Path(local_path or "").suffix or "(inline_text)"
        parsed_by_parser[suffix] = parsed_by_parser.get(suffix, 0) + 1
    stats["parsed_by_parser"] = parsed_by_parser

    unsupported_rows = conn.execute(
        "SELECT text_status, COUNT(*) FROM policy_documents WHERE text_status IN "
        "('unsupported_type', 'parser_unavailable') GROUP BY text_status"
    ).fetchall()
    stats["unsupported_by_type"] = {status: count for status, count in unsupported_rows}

    return stats


def _classify_with_policy_terms_flag(product, has_policy_terms: bool) -> str:
    """classify_public_product_readiness() takes a document list and derives
    has_policy_terms from it; here we've already determined that flag from
    document_registry directly (the authoritative post-reconciliation
    source), so build a minimal stand-in document list of the right shape
    rather than duplicating the readiness rules here.
    """
    from policy_data_contract import PublicDocumentRecord

    documents = (
        [PublicDocumentRecord(source=product.source, source_product_id=product.source_product_id,
                               document_type=DocumentType.POLICY_TERMS.value, title="")]
        if has_policy_terms
        else []
    )
    return classify_public_product_readiness(product, documents)


def _customer_policy_report(conn) -> dict[str, Any]:
    policy_rows = conn.execute(
        "SELECT id, profile_id, product_id, company_name, policy_name, policy_no, "
        "role, status, annual_premium, effective_date, source_document_id FROM customer_policies"
    ).fetchall()

    coverage_rows = conn.execute("SELECT policy_id, coverage_key, amount FROM customer_policy_coverages").fetchall()
    coverages_by_policy: dict[int, dict[str, float]] = {}
    for policy_id, coverage_key, amount in coverage_rows:
        coverages_by_policy.setdefault(policy_id, {})[coverage_key] = amount

    stats = {
        "customer_policies_total": 0,
        "by_readiness": {level.value: 0 for level in ReadinessLevel},
        "ready_for_policy_check": 0,
        "missing_policy_no": 0,
        "missing_premium": 0,
        "missing_effective_date": 0,
        "missing_coverages": 0,
        "missing_terms_source": 0,
    }

    for row in policy_rows:
        (policy_id, profile_id, product_id, company_name, policy_name, policy_no, role, status, annual_premium,
         effective_date, source_document_id) = row
        record = CustomerPolicyRecord(
            profile_id=profile_id,
            company_name=company_name,
            policy_name=policy_name,
            policy_no=policy_no or None,
            role=role or None,
            status=status or None,
            annual_premium=annual_premium or None,
            effective_date=effective_date or None,
            product_id=product_id or None,
            source_document_id=source_document_id,
            coverages=coverages_by_policy.get(policy_id, {}),
        )
        result = validate_customer_policy_record(record)
        readiness = classify_customer_policy_readiness(record)

        stats["customer_policies_total"] += 1
        stats["by_readiness"][readiness] += 1
        if readiness == ReadinessLevel.READY_FOR_POLICY_CHECK.value:
            stats["ready_for_policy_check"] += 1
        if "policy_no" in result.warnings:
            stats["missing_policy_no"] += 1
        if "annual_premium" in result.warnings:
            stats["missing_premium"] += 1
        if "effective_date" in result.warnings:
            stats["missing_effective_date"] += 1
        if "coverages" in result.warnings:
            stats["missing_coverages"] += 1
        if "terms_source" in result.warnings:
            stats["missing_terms_source"] += 1

    return stats


def _claim_info_report(conn) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT source_record_id, document_type FROM document_registry "
        "WHERE document_type IN (?, ?)",
        (DocumentType.CLAIM_DOCUMENT.value, DocumentType.CLAIM_PROCEDURE.value),
    ).fetchall()

    products_with_claim_document: set[int] = set()
    products_with_claim_procedure: set[int] = set()
    all_products: set[int] = set()
    for source_record_id, document_type in rows:
        all_products.add(source_record_id)
        if document_type == DocumentType.CLAIM_DOCUMENT.value:
            products_with_claim_document.add(source_record_id)
        elif document_type == DocumentType.CLAIM_PROCEDURE.value:
            products_with_claim_procedure.add(source_record_id)

    return {
        "claim_info_total": len(all_products),
        "claim_procedure_available": len(products_with_claim_procedure),
        "claim_documents_available": len(products_with_claim_document),
    }


def build_report() -> dict[str, Any]:
    with get_inventory_connection() as conn:
        return {
            "public_products": _public_product_report(conn),
            "customer_policies": _customer_policy_report(conn),
            "claim_info": _claim_info_report(conn),
        }


def main() -> None:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
