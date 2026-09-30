"""Policy Data Contract -- the shape every source (TII, IB, company adapters,
customer OCR upload) must convert into before anything downstream (RAG,
policy health-check, claim prep) can use it.

Why this exists
-----------------
Phases 2.5-2.9 built crawlers for three sources (TII's list index, IB's
company product lists, IB's per-product detail pages) that each emit their
own JSON shape (see scripts/sources/tii/source.py and
scripts/sources/ib_disclosure/source.py). Those shapes are fine as *source*
records -- exactly what was fetched, preserved as evidence -- but nothing
downstream (RAG chunking, policy health-check, claim document matching)
should have to know three different field-naming conventions, or guess
whether a given record has enough data to actually be useful yet. This
module is that translation + gate:

    source-specific record
            v
    PublicProductRecord / PublicDocumentRecord / CustomerPolicyRecord / ClaimInfoRecord
            v
    validate_*() -- structured errors/warnings, never a silent pass
            v
    classify_*_readiness() -- READY_FOR_RAG / READY_FOR_POLICY_CHECK / PARTIAL / INSUFFICIENT / NEEDS_REVIEW
            v
    DB tables (see each dataclass's docstring for its mapping)

Ground rules (matching every other parser in this codebase so far):
  - Never guess a company name, product name, or coverage amount that isn't
    actually present in the source data.
  - Never do fuzzy/LLM matching here -- normalization is string-rule-based
    only (mirrors scripts/inventory_repository.py's
    normalize_company_name/normalize_product_name, which this module reuses
    rather than re-implementing).
  - A record with missing fields is reported as missing, not silently
    dropped or silently treated as complete.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from inventory_repository import normalize_company_name, normalize_product_name  # noqa: E402


# ---------------------------------------------------------------------------
# Canonical document types
# ---------------------------------------------------------------------------


class DocumentType(str, Enum):
    POLICY_TERMS = "POLICY_TERMS"
    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"
    APPLICATION_FORM = "APPLICATION_FORM"
    RATE_TABLE = "RATE_TABLE"
    SHORT_TERM_RATE_TABLE = "SHORT_TERM_RATE_TABLE"
    COMMISSION_AND_EXPENSE_TABLE = "COMMISSION_AND_EXPENSE_TABLE"
    CLAIM_PROCEDURE = "CLAIM_PROCEDURE"
    CLAIM_DOCUMENT = "CLAIM_DOCUMENT"
    SIGNATORY_LIST = "SIGNATORY_LIST"
    RIDER = "RIDER"
    ENDORSEMENT = "ENDORSEMENT"
    OTHER = "OTHER"


# Longest/most-specific phrase first -- checked in order, first match wins.
# Covers the exact labels TII/IB actually use (see scripts/sources/tii/source.py
# and scripts/sources/ib_disclosure/source.py, whose own per-source keyword
# lists this supersedes as the system-wide canonical one).
_DOCUMENT_TYPE_KEYWORDS: tuple[tuple[str, DocumentType], ...] = (
    ("簽署人員名冊", DocumentType.SIGNATORY_LIST),
    ("簽署", DocumentType.SIGNATORY_LIST),
    ("理賠申請文件及程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠作業程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠申請程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠申請文件", DocumentType.CLAIM_DOCUMENT),
    ("理賠文件", DocumentType.CLAIM_DOCUMENT),
    ("理賠", DocumentType.CLAIM_DOCUMENT),
    ("附加費用率", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("退費係數", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("佣金", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("費用表", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("短期費率", DocumentType.SHORT_TERM_RATE_TABLE),
    ("費率說明", DocumentType.RATE_TABLE),
    ("費率", DocumentType.RATE_TABLE),
    ("要保書", DocumentType.APPLICATION_FORM),
    ("批註", DocumentType.ENDORSEMENT),
    ("附約", DocumentType.RIDER),
    ("附加條款", DocumentType.RIDER),
    ("保單條款", DocumentType.POLICY_TERMS),
    ("契約條款", DocumentType.POLICY_TERMS),
    ("條款", DocumentType.POLICY_TERMS),
    ("商品內容說明", DocumentType.PRODUCT_DESCRIPTION),
    ("商品說明", DocumentType.PRODUCT_DESCRIPTION),
    ("內容說明", DocumentType.PRODUCT_DESCRIPTION),
)


def normalize_document_type(label: str) -> str:
    """Map a document-type label to a canonical DocumentType value.

    Two input shapes are handled:
      - already a canonical value (e.g. a source's own parser already
        classified it as "POLICY_TERMS") -- passed through unchanged rather
        than re-run through keyword matching, which would fail (an enum
        value like "POLICY_TERMS" doesn't contain any Chinese keyword
        substring) and silently downgrade a confident upstream
        classification to OTHER.
      - free-text label (e.g. "保單條款", a TII/IB attachment's own visible
        text) -- matched against _DOCUMENT_TYPE_KEYWORDS.

    Returns DocumentType.OTHER.value if neither matches -- never guesses a
    specific type it isn't confident about.
    """
    text = (label or "").strip()
    if text in DocumentType.__members__:
        return DocumentType[text].value
    for keyword, doc_type in _DOCUMENT_TYPE_KEYWORDS:
        if keyword in text:
            return doc_type.value
    return DocumentType.OTHER.value


# ---------------------------------------------------------------------------
# Canonical coverage keys -- the ONLY keys customer_policy_coverages should
# ever see. Matches what the existing policy health-check / needs-assessment
# code actually reads (backend/services/policy_service.py,
# policy_report_service.py) -- adding a new key here without also updating
# that reader would make it silently invisible to health-check, so don't.
# ---------------------------------------------------------------------------

COVERAGE_KEYS: dict[str, str] = {
    "life": "壽險保障，單位：萬",
    "cancer": "癌症保障，單位：萬",
    "critical": "重大傷病保障，單位：萬",
    "accident": "意外保障，單位：萬",
    "daily": "住院日額，單位：元",
    "medical": "實支實付，單位：萬",
    "ltc": "長照保障，單位：萬/月",
}


def normalize_coverage_key(key: str) -> str | None:
    """Return `key` unchanged if it's one of COVERAGE_KEYS, else None.

    Deliberately does not try to map an unrecognized key to "the closest
    one" -- an unrecognized coverage type should surface as missing/unknown,
    not get silently folded into a different coverage bucket.
    """
    key = (key or "").strip().lower()
    return key if key in COVERAGE_KEYS else None


def normalize_policy_status(status: str) -> str:
    """Collapse status text variants to the small set customer_policies.status
    actually uses ('有效' | '停效' | '解約' | ...). Falls back to the input
    stripped, not a guess, if it doesn't match a known variant -- an unknown
    status should surface as itself for a human to check, not get silently
    coerced to '有效'.
    """
    text = (status or "").strip()
    if not text:
        return ""
    mapping = {
        "有效": "有效", "生效中": "有效", "承保中": "有效",
        "停效": "停效", "停止效力": "停效",
        "解約": "解約", "終止": "解約", "已解約": "解約",
        "到期": "期滿", "期滿": "期滿",
    }
    return mapping.get(text, text)


# ---------------------------------------------------------------------------
# Validation result + readiness levels
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)  # hard requirement violations
    warnings: list[str] = field(default_factory=list)  # soft gaps -- record is usable but incomplete


class ReadinessLevel(str, Enum):
    READY_FOR_RAG = "READY_FOR_RAG"
    READY_FOR_POLICY_CHECK = "READY_FOR_POLICY_CHECK"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# 1. PublicProductRecord -- TII / IB / company-site product data
# ---------------------------------------------------------------------------


@dataclass
class PublicProductRecord:
    """One public (non-customer) product, from any central-registry or
    company-site source.

    DB mapping: source_product_records (as-is, staging) -> product_families
    / product_versions (after reconcile_source_records.py matching) ->
    insurance_products (the pre-existing company-crawl table -- reconciling
    THAT table against product_versions is still open work, not done by this
    module; see the Phase 2 plan's `authority_level`/reconciliation design).
    """

    source: str
    source_product_id: str
    product_name: str

    product_code: str | None = None
    company_name: str | None = None
    company_uid: str | None = None
    insurance_type: str | None = None
    category: str | None = None
    sale_start_date: str | None = None
    sale_end_date: str | None = None
    status: str | None = None
    approval_date: str | None = None
    approval_number: str | None = None
    latest_approval_date: str | None = None
    latest_approval_number: str | None = None
    source_url: str | None = None
    detail_url: str | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass
class PublicDocumentRecord:
    """One document (terms, rate table, claim procedure, ...) tied to a
    PublicProductRecord via source_product_id.

    DB mapping: document_registry (as-is) -> document_snapshots (once
    downloaded) -> policy_documents / policy_document_chunks (once reconciled
    against insurance_products and RAG-chunked -- also open work; today's
    policy_documents rows come from the pre-existing company-crawl pipeline,
    not from this contract's document_registry rows).
    """

    source: str
    source_product_id: str
    document_type: str  # a DocumentType value -- run through normalize_document_type() first
    title: str

    document_url: str | None = None  # a real, fetchable URL
    postback_target: str | None = None  # set instead of document_url when the source has no static URL (e.g. IB LinkButtons)
    detail_url: str | None = None  # the page this document was found on
    content_type: str | None = None
    local_path: str | None = None
    checksum: str | None = None
    text_status: str = "pending"
    parsed_text: str | None = None
    raw_payload: dict = field(default_factory=dict)


def validate_public_product_record(record: PublicProductRecord) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not (record.product_name or "").strip():
        errors.append("product_name")
    if not (record.source_product_id or "").strip():
        errors.append("source_product_id")
    if not (record.company_name or "").strip():
        warnings.append("company_name")
    if not (record.approval_number or "").strip():
        warnings.append("approval_number")

    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def classify_public_product_readiness(
    record: PublicProductRecord,
    documents: list[PublicDocumentRecord] | None = None,
    *,
    source_conflict: bool = False,
) -> str:
    """See module docstring's rule table. Priority, checked in order:

      1. source_conflict=True (a caller-detected disagreement between two
         sources for "the same" product, e.g. Phase 3's METADATA_CONFLICT)
         -> NEEDS_REVIEW, regardless of anything else.
      2. No product_name at all -> INSUFFICIENT (the contract requires this;
         see validate_public_product_record).
      3. product_name + company_name + a POLICY_TERMS document -> READY_FOR_RAG.
      4. No company_name AND no documents at all (e.g. a bare TII
         ResultQueryAll row) -> INSUFFICIENT.
      5. Anything else with at least product_name -> PARTIAL (has *some*
         useful data -- a company name, or at least one document -- but not
         enough for RAG yet).
    """
    documents = documents or []
    if source_conflict:
        return ReadinessLevel.NEEDS_REVIEW.value
    if not (record.product_name or "").strip():
        return ReadinessLevel.INSUFFICIENT.value

    has_company = bool((record.company_name or "").strip())
    has_policy_terms = any(normalize_document_type(d.document_type) == DocumentType.POLICY_TERMS.value for d in documents)

    if has_company and has_policy_terms:
        return ReadinessLevel.READY_FOR_RAG.value
    if not has_company and not documents:
        return ReadinessLevel.INSUFFICIENT.value
    return ReadinessLevel.PARTIAL.value


# ---------------------------------------------------------------------------
# 2. CustomerPolicyRecord -- what a customer actually holds
# ---------------------------------------------------------------------------


@dataclass
class CustomerPolicyRecord:
    """One policy a customer holds, from manual entry or OCR extraction.

    DB mapping: customer_policies (main row) + customer_policy_coverages
    (one row per COVERAGE_KEYS entry present) + customer_policy_riders (one
    row per rider name) + customer_policy_uploads (the source file/OCR text,
    already written before this record is built -- source_document_id here
    is a policy_documents.id per the existing schema, kept as-is; it is NOT
    a customer_policy_uploads.id).
    """

    profile_id: str
    company_name: str
    policy_name: str

    policy_no: str | None = None
    role: str | None = None
    status: str | None = None
    annual_premium: float | None = None
    effective_date: str | None = None
    period_text: str | None = None
    product_id: str | None = None
    source_document_id: int | None = None
    coverages: dict[str, float] = field(default_factory=dict)  # key must be in COVERAGE_KEYS
    riders: list[str] = field(default_factory=list)
    raw_text: str | None = None
    raw_payload: dict = field(default_factory=dict)


def validate_customer_policy_record(record: CustomerPolicyRecord) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    has_company = bool((record.company_name or "").strip())
    has_policy_name = bool((record.policy_name or "").strip())
    if not has_company and not has_policy_name:
        errors.append("company_name_or_policy_name")

    if not (record.policy_no or "").strip():
        warnings.append("policy_no")
    if not record.annual_premium:
        warnings.append("annual_premium")
    if not (record.effective_date or "").strip():
        warnings.append("effective_date")
    if not record.coverages:
        warnings.append("coverages")
    elif any(normalize_coverage_key(k) is None for k in record.coverages):
        bad_keys = [k for k in record.coverages if normalize_coverage_key(k) is None]
        warnings.append(f"unrecognized_coverage_keys:{','.join(bad_keys)}")
    if not record.product_id and not record.source_document_id:
        # "terms_source" is a logical field, not a literal dataclass attribute --
        # it means "we have no way to trace this policy back to its actual
        # policy-terms document", which matters for policy health-check even
        # though no single input field is named that.
        warnings.append("terms_source")

    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


def classify_customer_policy_readiness(record: CustomerPolicyRecord) -> str:
    """See module docstring's rule table.

      - Neither company_name nor policy_name at all (e.g. only an uploaded
        file's OCR text exists so far) -> INSUFFICIENT.
      - All of company/policy name/policy_no/premium/effective_date present,
        PLUS coverages AND a terms source -> READY_FOR_POLICY_CHECK.
      - Otherwise, as long as there's at least a company or policy name ->
        PARTIAL (this is the "missing coverages/terms_source but has basic
        policy data" case).
    """
    has_company = bool((record.company_name or "").strip())
    has_policy_name = bool((record.policy_name or "").strip())
    if not has_company and not has_policy_name:
        return ReadinessLevel.INSUFFICIENT.value

    basic_complete = (
        has_company
        and has_policy_name
        and bool((record.policy_no or "").strip())
        and bool(record.annual_premium)
        and bool((record.effective_date or "").strip())
    )
    has_coverages = bool(record.coverages)
    has_terms_source = bool(record.product_id or record.source_document_id)

    if basic_complete and has_coverages and has_terms_source:
        return ReadinessLevel.READY_FOR_POLICY_CHECK.value
    return ReadinessLevel.PARTIAL.value


# ---------------------------------------------------------------------------
# 3. ClaimInfoRecord -- claim documents/procedure for a product
# ---------------------------------------------------------------------------


@dataclass
class ClaimInfoRecord:
    """Claim-related info for one product -- required documents and/or the
    claim procedure text/file.

    DB mapping: no dedicated table yet. For now this maps into
    document_registry with document_type in {CLAIM_DOCUMENT, CLAIM_PROCEDURE}
    (what scripts/resolve_ib_product_details.py already writes) -- a
    dedicated claim-rules table is future work, not part of this contract.
    claim_cases (the customer-facing claim-tracking table) is a different,
    already-existing thing this record does not feed.
    """

    source: str
    source_product_id: str
    company_name: str | None = None
    product_name: str | None = None
    claim_type: str | None = None
    required_documents: list[str] = field(default_factory=list)
    claim_procedure_text: str | None = None
    document_url: str | None = None
    local_path: str | None = None
    raw_payload: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Source-specific converters -- TII / IB source records -> this contract.
# Company adapters (scripts/adapters/*.py) and the live OCR/policy-extraction
# pipeline (backend/services/policy_extraction_service.py) are NOT wired to
# this contract by this module -- see scripts/report_policy_data_readiness.py's
# module docstring for why that's a deliberate scope boundary, not an
# oversight.
# ---------------------------------------------------------------------------


def from_tii_source_record(payload: dict) -> tuple[PublicProductRecord, list[PublicDocumentRecord]]:
    """Convert a scripts/sources/tii/source.py SourceProductRecord.to_dict()
    payload (as written to backend/data/tii_source_records.jsonl or
    backend/data/tii_result_records.jsonl) into the contract shape.
    """
    product = PublicProductRecord(
        source="tii",
        source_product_id=payload.get("source_product_id") or "",
        product_name=payload.get("product_name") or "",
        product_code=payload.get("product_code") or None,
        company_name=payload.get("company_name") or None,
        insurance_type=payload.get("insurance_type") or None,
        category=payload.get("insurance_category") or None,
        sale_start_date=payload.get("sale_start_date") or None,
        sale_end_date=payload.get("sale_end_date") or None,
        approval_date=payload.get("approval_date") or None,
        approval_number=payload.get("approval_number") or None,
        source_url=payload.get("source_product_url") or None,
        detail_url=payload.get("detail_url") or None,
        raw_payload=payload,
    )
    documents = [
        PublicDocumentRecord(
            source="tii",
            source_product_id=product.source_product_id,
            document_type=normalize_document_type(doc.get("document_type") or doc.get("label") or ""),
            title=doc.get("label") or "",
            document_url=doc.get("url") or None,
            detail_url=payload.get("detail_url") or None,
            raw_payload=doc,
        )
        for doc in payload.get("documents") or []
    ]
    return product, documents


def from_ib_source_record(payload: dict) -> tuple[PublicProductRecord, list[PublicDocumentRecord]]:
    """Convert a scripts/sources/ib_disclosure/source.py SourceProductRecord.to_dict()
    payload (as written to backend/data/ib_company_products.jsonl) into the
    contract shape. Approval fields come from raw_payload["detail"] once
    scripts/resolve_ib_product_details.py has run -- absent until then, same
    as the source record itself.
    """
    detail = (payload.get("raw_payload") or payload).get("detail") if isinstance(payload.get("raw_payload"), dict) else None
    detail = detail or {}
    product = PublicProductRecord(
        source="ib_disclosure",
        source_product_id=payload.get("source_product_id") or "",
        product_name=payload.get("product_name") or "",
        product_code=payload.get("product_code") or None,
        company_name=payload.get("company_name") or None,
        company_uid=payload.get("company_uid") or None,
        insurance_type=payload.get("insurance_type") or detail.get("insurance_type") or None,
        category=payload.get("insurance_category") or None,
        approval_date=payload.get("approval_date") or detail.get("approval_date") or None,
        approval_number=payload.get("approval_number") or detail.get("approval_number") or None,
        latest_approval_date=payload.get("latest_approval_date") or detail.get("latest_approval_date") or None,
        latest_approval_number=payload.get("latest_approval_number") or detail.get("latest_approval_number") or None,
        source_url=payload.get("source_product_url") or None,
        detail_url=payload.get("detail_url") or None,
        raw_payload=payload,
    )
    documents = [
        PublicDocumentRecord(
            source="ib_disclosure",
            source_product_id=product.source_product_id,
            document_type=normalize_document_type(doc.get("document_type") or doc.get("label") or ""),
            title=doc.get("label") or "",
            document_url=doc.get("url") or None,
            postback_target=doc.get("source_document_id") or None,
            detail_url=payload.get("detail_url") or None,
            raw_payload=doc,
        )
        for doc in payload.get("documents") or []
    ]
    return product, documents


# backend/services/policy_extraction_service.py's own field names -> this
# contract's canonical COVERAGE_KEYS. Only fields with an unambiguous mapping
# are listed -- see _OCR_UNMAPPED_FIELDS for the rest.
_OCR_COVERAGE_KEY_MAP: dict[str, str] = {
    "life_coverage": "life",
    "medical_daily": "daily",
    "accident_coverage": "accident",
    "cancer_coverage": "cancer",
}

# OCR fields with no defined canonical coverage key yet. "disability_monthly"
# could plausibly become "ltc" (long-term care) or a new "disability" key,
# but guessing which one here -- without a product/policy owner deciding --
# is exactly the kind of invented-field mapping this contract exists to
# avoid. Kept in raw_payload verbatim and surfaced as a validation warning
# instead of silently dropped or silently mapped.
_OCR_UNMAPPED_FIELDS: tuple[str, ...] = ("disability_monthly",)

# extract_policy_coverage()'s own placeholder for "couldn't find this" --
# treated as empty, not as a literal company/policy name, the same way
# policy_service.py already treats its own "未知保險公司" placeholder as
# absent (see evaluate_policy_completeness()'s `!= "未知保險公司"` checks).
_OCR_UNKNOWN_SENTINEL = "未知"


def from_ocr_extraction(
    ocr_result: dict,
    profile_id: str,
    *,
    product_id: str | None = None,
    source_document_id: int | None = None,
    raw_text: str | None = None,
) -> tuple[CustomerPolicyRecord, ValidationResult]:
    """Convert backend/services/policy_extraction_service.py's
    extract_policy_coverage() output into a CustomerPolicyRecord.

    Does NOT write to the database -- same as every other converter in this
    module, the caller still owns persisting the result (via
    backend/services/policy_service.py's create_policy()/update_policy(),
    which already expects exactly this contract's coverage keys -- see its
    own COVERAGE_META). This function exists so the OCR service's own
    invented field names never reach that call directly.
    """
    coverages: dict[str, float] = {}
    for ocr_key, coverage_key in _OCR_COVERAGE_KEY_MAP.items():
        value = ocr_result.get(ocr_key)
        if value:
            coverages[coverage_key] = float(value)

    def _clean(value: Any) -> str:
        text = str(value or "").strip()
        return "" if text == _OCR_UNKNOWN_SENTINEL else text

    record = CustomerPolicyRecord(
        profile_id=profile_id,
        company_name=_clean(ocr_result.get("company")),
        policy_name=_clean(ocr_result.get("policy_name")),
        product_id=product_id,
        source_document_id=source_document_id,
        coverages=coverages,
        raw_text=raw_text,
        raw_payload=dict(ocr_result),
    )

    result = validate_customer_policy_record(record)
    unmapped = {f: ocr_result[f] for f in _OCR_UNMAPPED_FIELDS if ocr_result.get(f)}
    if unmapped:
        result.warnings.append("unmapped_ocr_fields:" + ",".join(f"{k}={v}" for k, v in unmapped.items()))

    return record, result


# Re-exported so callers doing string-based company/product matching don't
# need a second import for the normalization this module already depends on.
__all__ = [
    "DocumentType",
    "normalize_document_type",
    "COVERAGE_KEYS",
    "normalize_coverage_key",
    "normalize_policy_status",
    "normalize_company_name",
    "normalize_product_name",
    "ValidationResult",
    "ReadinessLevel",
    "PublicProductRecord",
    "PublicDocumentRecord",
    "validate_public_product_record",
    "classify_public_product_readiness",
    "CustomerPolicyRecord",
    "validate_customer_policy_record",
    "classify_customer_policy_readiness",
    "ClaimInfoRecord",
    "from_tii_source_record",
    "from_ib_source_record",
    "from_ocr_extraction",
]
