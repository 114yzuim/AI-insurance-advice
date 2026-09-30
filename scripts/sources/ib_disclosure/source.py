"""Unified output shape for data pulled from IB (保險業公開資訊觀測站,
ins-info.ib.gov.tw) product disclosure pages.

SCOPE NOTE -- read scripts/sources/ib_disclosure/README.md and
property_parser.py's module docstring before extending this. In short: this
phase only parses whatever HTML a given URL returns, never submits IB's
product search form (it's a plain ASP.NET postback, no CAPTCHA, but this
phase's instructions are to only read explicit links already in the page,
not to drive postbacks), and never guesses at a document-type label it
can't classify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DocumentType(str, Enum):
    """IB's document-type vocabulary, distinct from (but overlapping)
    scripts/sources/tii/source.py's -- kept separate because IB's disclosure
    categories don't map 1:1 onto TII's (e.g. IB separates SHORT_TERM_RATE_TABLE
    and COMMISSION_AND_EXPENSE_TABLE out from a generic rate table, and
    separates CLAIM_PROCEDURE from CLAIM_DOCUMENT).
    """

    POLICY_TERMS = "POLICY_TERMS"  # 保單條款
    PRODUCT_DESCRIPTION = "PRODUCT_DESCRIPTION"  # 商品說明書 / 商品內容說明
    APPLICATION_FORM = "APPLICATION_FORM"  # 要保書
    RATE_TABLE = "RATE_TABLE"  # 費率表
    SHORT_TERM_RATE_TABLE = "SHORT_TERM_RATE_TABLE"  # 短期費率表
    COMMISSION_AND_EXPENSE_TABLE = "COMMISSION_AND_EXPENSE_TABLE"  # 佣金及費用表
    CLAIM_DOCUMENT = "CLAIM_DOCUMENT"  # 理賠文件
    CLAIM_PROCEDURE = "CLAIM_PROCEDURE"  # 理賠作業程序
    SIGNATORY_LIST = "SIGNATORY_LIST"  # 簽署人員名冊
    OTHER = "OTHER"


# Ordered so the first substring match wins (more specific labels first).
_DOCUMENT_TYPE_KEYWORDS: tuple[tuple[str, DocumentType], ...] = (
    ("簽署", DocumentType.SIGNATORY_LIST),
    ("理賠作業程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠程序", DocumentType.CLAIM_PROCEDURE),
    ("理賠", DocumentType.CLAIM_DOCUMENT),
    ("佣金", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("費用表", DocumentType.COMMISSION_AND_EXPENSE_TABLE),
    ("短期費率", DocumentType.SHORT_TERM_RATE_TABLE),
    ("費率", DocumentType.RATE_TABLE),
    ("要保書", DocumentType.APPLICATION_FORM),
    ("保單條款", DocumentType.POLICY_TERMS),
    ("條款", DocumentType.POLICY_TERMS),
    ("商品說明", DocumentType.PRODUCT_DESCRIPTION),
    ("商品內容說明", DocumentType.PRODUCT_DESCRIPTION),
)


def classify_document_label(label: str) -> DocumentType:
    text = (label or "").strip()
    for keyword, doc_type in _DOCUMENT_TYPE_KEYWORDS:
        if keyword in text:
            return doc_type
    return DocumentType.OTHER


@dataclass
class IbDocumentLink:
    """One document reference found on an IB disclosure page.

    `url` may be "" -- verified live (2026-09-13): every actual file
    download on IB's detail pages (property5-1-N.aspx) is an ASP.NET
    LinkButton wired to `javascript:__doPostBack('ctl00$MainContent$LinkButtonN','')`,
    never a plain `<a href="....pdf">`. Per this project's "don't fabricate
    a URL" rule (the same one already applied to the short-term-rate-table
    case), a LinkButton-only reference is still recorded -- its visible
    filename as `label`, its postback target as `source_document_id` -- but
    with `url=""`, not a guessed-at file path. Resolving what that postback
    actually returns (a redirect to a real file URL? streamed bytes with no
    separate URL at all?) is unverified and out of scope for this phase; see
    scripts/sources/ib_disclosure/README.md.
    """

    label: str
    url: str = ""
    document_type: DocumentType = DocumentType.OTHER
    source_document_id: str | None = None  # the __doPostBack event target, when url is empty
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.document_type is DocumentType.OTHER:
            self.document_type = classify_document_label(self.label)


@dataclass
class SourceProductRecord:
    """Normalized view of one IB product row/page.

    Like scripts/sources/tii/source.py's record of the same name, this is a
    *source* record, not yet a product_versions row -- Phase 3's
    reconcile_source_records.py decides matching/canonical status.
    """

    source_product_id: str  # "{company_uid}:{product_code}" -- see property_parser.py
    detail_url: str  # canonical: the function=1 (基本資訊) page for this product
    fetched_at: str

    source_product_url: str | None = None  # the company query page this record was found on
    company_name: str | None = None
    company_uid: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    insurance_category: str | None = None  # 'property' | 'life', from the company seed -- not printed by IB itself
    insurance_type: str | None = None  # 險別
    sale_start_date: str | None = None  # not exposed by IB -- kept for shape-parity with other sources
    sale_end_date: str | None = None
    approval_date: str | None = None
    approval_number: str | None = None
    latest_approval_date: str | None = None
    latest_approval_number: str | None = None
    last_sent_to_tii_date: str | None = None  # 最近一次檢送保險商品資料庫之日期
    last_sent_to_tii_number: str | None = None  # 最近一次檢送保險商品資料庫之文號

    documents: list[IbDocumentLink] = field(default_factory=list)
    raw_fields: dict = field(default_factory=dict)
    source_html_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "source": "ib_disclosure",
            "source_product_id": self.source_product_id,
            "detail_url": self.detail_url,
            "source_product_url": self.source_product_url,
            "fetched_at": self.fetched_at,
            "company_name": self.company_name,
            "company_uid": self.company_uid,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "insurance_category": self.insurance_category,
            "insurance_type": self.insurance_type,
            "sale_start_date": self.sale_start_date,
            "sale_end_date": self.sale_end_date,
            "approval_date": self.approval_date,
            "approval_number": self.approval_number,
            "latest_approval_date": self.latest_approval_date,
            "latest_approval_number": self.latest_approval_number,
            "last_sent_to_tii_date": self.last_sent_to_tii_date,
            "last_sent_to_tii_number": self.last_sent_to_tii_number,
            "documents": [
                {
                    "label": d.label,
                    "url": d.url,
                    "document_type": d.document_type.value,
                    "source_document_id": d.source_document_id,
                    "metadata": d.metadata,
                }
                for d in self.documents
            ],
            "raw_fields": self.raw_fields,
            "source_html_path": self.source_html_path,
        }
