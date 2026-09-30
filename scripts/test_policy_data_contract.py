"""Tests for scripts/policy_data_contract.py.

No pytest dependency in this repo (see backend/requirements.txt) -- uses
stdlib unittest, matching this project's existing preference for
plain-Python verification scripts over adding a new test framework.

Run: python scripts/test_policy_data_contract.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from policy_data_contract import (  # noqa: E402
    ClaimInfoRecord,
    CustomerPolicyRecord,
    DocumentType,
    PublicDocumentRecord,
    PublicProductRecord,
    ReadinessLevel,
    classify_customer_policy_readiness,
    classify_public_product_readiness,
    from_ib_source_record,
    from_ocr_extraction,
    from_tii_source_record,
    normalize_document_type,
    validate_customer_policy_record,
    validate_public_product_record,
)


class TestPublicProductReadiness(unittest.TestCase):
    def test_tii_bare_list_record_is_insufficient(self):
        """A record with only productId/product_name/dates (TII's
        ResultQueryAll.aspx shape -- no company_name, no documents) must
        never be reported as RAG-ready.
        """
        payload = {
            "source": "tii",
            "source_product_id": "132132206007200000",
            "detail_url": "https://insprod.tii.org.tw/DetailList.aspx?productId=132132206007200000",
            "product_name": "安達產物Goods purchased by the Insured on CIF terms",
            "company_name": "",
            "sale_start_date": "108/07/25",
            "documents": [],
        }
        product, documents = from_tii_source_record(payload)
        readiness = classify_public_product_readiness(product, documents)
        self.assertIn(readiness, (ReadinessLevel.INSUFFICIENT.value, ReadinessLevel.PARTIAL.value))
        self.assertNotEqual(readiness, ReadinessLevel.READY_FOR_RAG.value)
        # this specific shape (no company, no documents at all) is the
        # explicit INSUFFICIENT case from the module docstring
        self.assertEqual(readiness, ReadinessLevel.INSUFFICIENT.value)

    def test_ib_record_with_company_product_and_terms_is_ready_for_rag(self):
        payload = {
            "source": "ib_disclosure",
            "source_product_id": "03557115:1011616301000401",
            "detail_url": "https://ins-info.ib.gov.tw/customer/property5-1-1.aspx?UID=03557115&proc=1011616301000401",
            "source_product_url": "https://ins-info.ib.gov.tw/customer/Property_Layout.aspx?UID=03557115",
            "company_name": "臺灣產物保險股份有限公司",
            "company_uid": "03557115",
            "product_code": "1011616301000401",
            "product_name": "臺灣產物新海外突發疾病醫療健康保險附約",
            "insurance_type": "健康保險",
            "approval_date": "2026-06-25",
            "approval_number": "產精算字第1150001758號函備查",
            "documents": [
                {"label": "保單條款", "url": "", "document_type": "POLICY_TERMS", "source_document_id": "LinkButton1"},
            ],
        }
        product, documents = from_ib_source_record(payload)
        readiness = classify_public_product_readiness(product, documents)
        self.assertEqual(readiness, ReadinessLevel.READY_FOR_RAG.value)

    def test_source_conflict_forces_needs_review(self):
        product = PublicProductRecord(source="tii", source_product_id="x", product_name="foo", company_name="bar")
        readiness = classify_public_product_readiness(
            product, [PublicDocumentRecord(source="tii", source_product_id="x", document_type="POLICY_TERMS", title="t")],
            source_conflict=True,
        )
        self.assertEqual(readiness, ReadinessLevel.NEEDS_REVIEW.value)

    def test_missing_product_name_is_invalid(self):
        record = PublicProductRecord(source="tii", source_product_id="x", product_name="")
        result = validate_public_product_record(record)
        self.assertFalse(result.is_valid)
        self.assertIn("product_name", result.errors)

    def test_missing_source_product_id_is_invalid(self):
        record = PublicProductRecord(source="tii", source_product_id="", product_name="foo")
        result = validate_public_product_record(record)
        self.assertFalse(result.is_valid)
        self.assertIn("source_product_id", result.errors)


class TestCustomerPolicyReadiness(unittest.TestCase):
    def _complete_record(self, **overrides) -> CustomerPolicyRecord:
        base = dict(
            profile_id="p1",
            company_name="國泰人壽",
            policy_name="美好人生終身壽險",
            policy_no="A123456",
            annual_premium=12000.0,
            effective_date="2020-01-01",
            coverages={"life": 500.0},
            product_id="prod-1",
        )
        base.update(overrides)
        return CustomerPolicyRecord(**base)

    def test_complete_record_is_ready_for_policy_check(self):
        record = self._complete_record()
        self.assertEqual(classify_customer_policy_readiness(record), ReadinessLevel.READY_FOR_POLICY_CHECK.value)

    def test_missing_coverages_is_partial(self):
        record = self._complete_record(coverages={})
        self.assertEqual(classify_customer_policy_readiness(record), ReadinessLevel.PARTIAL.value)
        result = validate_customer_policy_record(record)
        self.assertIn("coverages", result.warnings)

    def test_missing_terms_source_reports_terms_source_warning(self):
        record = self._complete_record(product_id=None, source_document_id=None)
        result = validate_customer_policy_record(record)
        self.assertIn("terms_source", result.warnings)
        self.assertEqual(classify_customer_policy_readiness(record), ReadinessLevel.PARTIAL.value)

    def test_only_raw_text_is_insufficient(self):
        record = CustomerPolicyRecord(
            profile_id="p1", company_name="", policy_name="", raw_text="掃描出來的原始文字..."
        )
        result = validate_customer_policy_record(record)
        self.assertFalse(result.is_valid)
        self.assertEqual(classify_customer_policy_readiness(record), ReadinessLevel.INSUFFICIENT.value)


class TestDocumentTypeNormalization(unittest.TestCase):
    def test_policy_terms(self):
        self.assertEqual(normalize_document_type("保單條款"), DocumentType.POLICY_TERMS.value)

    def test_short_term_rate_table(self):
        self.assertEqual(normalize_document_type("短期費率表"), DocumentType.SHORT_TERM_RATE_TABLE.value)

    def test_claim_procedure_composite_label(self):
        self.assertEqual(normalize_document_type("理賠申請文件及程序"), DocumentType.CLAIM_PROCEDURE.value)

    def test_commission_and_expense_table_composite_label(self):
        self.assertEqual(
            normalize_document_type("銷售予金融消費者之保險商品預定附加費用率與保費退費係數表"),
            DocumentType.COMMISSION_AND_EXPENSE_TABLE.value,
        )

    def test_unrecognized_label_is_other(self):
        self.assertEqual(normalize_document_type("完全沒有對應的文字"), DocumentType.OTHER.value)


class TestOcrExtractionMapper(unittest.TestCase):
    def _ocr_result(self, **overrides) -> dict:
        base = dict(
            policy_name="美好人生終身壽險",
            company="國泰人壽",
            life_coverage=500,
            medical_daily=1500,
            accident_coverage=200,
            cancer_coverage=100,
            disability_monthly=20000,
            notes="",
        )
        base.update(overrides)
        return base

    def test_known_fields_map_to_canonical_coverage_keys(self):
        record, _ = from_ocr_extraction(self._ocr_result(), profile_id="p1")
        self.assertEqual(
            record.coverages,
            {"life": 500.0, "daily": 1500.0, "accident": 200.0, "cancer": 100.0},
        )
        self.assertNotIn("disability", record.coverages)
        self.assertNotIn("ltc", record.coverages)

    def test_disability_monthly_is_not_dropped_silently(self):
        record, result = from_ocr_extraction(self._ocr_result(), profile_id="p1")
        self.assertEqual(record.raw_payload["disability_monthly"], 20000)
        self.assertTrue(any("unmapped_ocr_fields" in w and "disability_monthly" in w for w in result.warnings))

    def test_unknown_sentinel_treated_as_missing(self):
        record, result = from_ocr_extraction(
            self._ocr_result(policy_name="未知", company="未知"), profile_id="p1"
        )
        self.assertEqual(record.company_name, "")
        self.assertEqual(record.policy_name, "")
        self.assertFalse(result.is_valid)
        self.assertIn("company_name_or_policy_name", result.errors)

    def test_raw_text_and_payload_preserved(self):
        ocr_result = self._ocr_result()
        record, _ = from_ocr_extraction(ocr_result, profile_id="p1", raw_text="原始 OCR 文字")
        self.assertEqual(record.raw_text, "原始 OCR 文字")
        self.assertEqual(record.raw_payload, ocr_result)

    def test_coverage_keys_are_canonical_only(self):
        record, _ = from_ocr_extraction(self._ocr_result(), profile_id="p1")
        from policy_data_contract import COVERAGE_KEYS

        for key in record.coverages:
            self.assertIn(key, COVERAGE_KEYS)


class TestClaimInfoRecordShape(unittest.TestCase):
    def test_construction_does_not_require_optional_fields(self):
        record = ClaimInfoRecord(source="ib_disclosure", source_product_id="03557115:x")
        self.assertEqual(record.required_documents, [])
        self.assertIsNone(record.claim_procedure_text)


if __name__ == "__main__":
    unittest.main()
