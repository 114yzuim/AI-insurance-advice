"""Unified output shape for data pulled from the TII (保發中心) product database.

IMPORTANT SCOPE NOTE
---------------------
insprod.tii.org.tw gates its search/list forms behind an image CAPTCHA
("查詢識別碼") -- every query, including a bare company/type filter with no
keyword, requires it. We do not automate solving that CAPTCHA (that would be
bypassing bot-detection), so there is no `list_parser.py` / automated
discovery in this package: nothing here can enumerate "all TII products" on
its own.

What *is* in scope: once a human has solved the CAPTCHA in their own browser
and reached a specific product's detail page, the detail page itself and its
attachment links (`Open2.ashx?id=<uuid>`) are plain GET-able URLs. This
package turns one such detail page (given its URL/HTML by a human, or fetched
with a human-provided session cookie) into a structured record. See
client.py's module docstring for the exact hand-off contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DocumentType(str, Enum):
    """Mirrors the document_expectation_rules vocabulary planned for Phase 4."""

    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"  # 商品內容說明
    POLICY_TERMS = "POLICY_TERMS"  # 保單條款
    APPLICATION_FORM = "APPLICATION_FORM"  # 要保書
    RATE_TABLE = "RATE_TABLE"  # 費率表
    RATE_EXPLANATION = "RATE_EXPLANATION"  # 費率說明
    CLAIM_DOCUMENT = "CLAIM_DOCUMENT"  # 理賠相關文件
    SIGNATORY_LIST = "SIGNATORY_LIST"  # 簽署人員名冊
    RIDER_TERMS = "RIDER_TERMS"  # 附約條款
    ENDORSEMENT = "ENDORSEMENT"  # 批註條款
    OTHER = "OTHER"


# Ordered so the first substring match wins (more specific labels first).
_DOCUMENT_TYPE_KEYWORDS: tuple[tuple[str, DocumentType], ...] = (
    ("簽署", DocumentType.SIGNATORY_LIST),
    ("批註", DocumentType.ENDORSEMENT),
    ("附約", DocumentType.RIDER_TERMS),
    ("理賠", DocumentType.CLAIM_DOCUMENT),
    ("費率說明", DocumentType.RATE_EXPLANATION),
    ("費率", DocumentType.RATE_TABLE),
    ("要保書", DocumentType.APPLICATION_FORM),
    ("保單條款", DocumentType.POLICY_TERMS),
    ("條款", DocumentType.POLICY_TERMS),
    ("商品內容說明", DocumentType.PRODUCT_DESCRIPTION),
    ("內容說明", DocumentType.PRODUCT_DESCRIPTION),
)


def classify_document_label(label: str) -> DocumentType:
    text = (label or "").strip()
    for keyword, doc_type in _DOCUMENT_TYPE_KEYWORDS:
        if keyword in text:
            return doc_type
    return DocumentType.OTHER


@dataclass
class TiiDocumentLink:
    """One attachment found on a TII product detail page."""

    label: str
    url: str  # absolute https://insprod.tii.org.tw/Open2.ashx?id=<uuid>
    open_id: str  # the `id` query-string value, extracted for dedup/keying
    document_type: DocumentType = DocumentType.OTHER

    def __post_init__(self) -> None:
        if self.document_type is DocumentType.OTHER:
            self.document_type = classify_document_label(self.label)


@dataclass
class SourceProductRecord:
    """Normalized view of one TII product detail page.

    This is a *source* record (raw-ish, one per TII detail page fetch) -- it
    is not yet a `product_versions` row. Phase 2's reconciliation step is
    responsible for matching/merging this against company-adapter records and
    deciding version/canonical_status.
    """

    source_product_id: str  # TII's own product id (from the detail URL)
    detail_url: str
    fetched_at: str  # ISO 8601 UTC timestamp

    company_code: str | None = None
    company_name: str | None = None
    product_name: str | None = None
    insurance_category: str | None = None  # raw 財產保險/人身保險
    insurance_type: str | None = None  # raw 保險類別, e.g. 傳統型壽險
    sale_start_date: str | None = None  # as printed by TII, usually ROC yyy/mm/dd
    sale_end_date: str | None = None
    approval_date: str | None = None
    approval_number: str | None = None
    filing_number: str | None = None
    review_method: str | None = None

    documents: list[TiiDocumentLink] = field(default_factory=list)

    # Every label/value pair the detail-page parser found, verbatim, even ones
    # we don't have a named field for yet. Kept so nothing is silently
    # dropped while the real page structure is still being verified against
    # a live sample.
    raw_fields: dict[str, str] = field(default_factory=dict)

    # Path (relative to repo root) of the raw HTML snapshot this record was
    # parsed from, for provenance / re-parsing after a parser bug fix.
    source_html_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "source": "tii",
            "source_product_id": self.source_product_id,
            "detail_url": self.detail_url,
            "fetched_at": self.fetched_at,
            "company_code": self.company_code,
            "company_name": self.company_name,
            "product_name": self.product_name,
            "insurance_category": self.insurance_category,
            "insurance_type": self.insurance_type,
            "sale_start_date": self.sale_start_date,
            "sale_end_date": self.sale_end_date,
            "approval_date": self.approval_date,
            "approval_number": self.approval_number,
            "filing_number": self.filing_number,
            "review_method": self.review_method,
            "documents": [
                {
                    "label": d.label,
                    "url": d.url,
                    "open_id": d.open_id,
                    "document_type": d.document_type.value,
                }
                for d in self.documents
            ],
            "raw_fields": self.raw_fields,
            "source_html_path": self.source_html_path,
        }
