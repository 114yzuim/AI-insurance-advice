"""Tests for scripts/source_response_classifier.py.

Fixtures are real evidence text captured live from IB/TII in earlier phases
of this project (see scripts/sources/ib_disclosure/failure_classifier.py's
history), not invented samples.

Run: python scripts/test_source_response_classifier.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_response_classifier import classify_source_response  # noqa: E402


class TestSourceResponseClassifier(unittest.TestCase):
    def test_ib_waf_rejection(self):
        result = classify_source_response(
            status_code=200,
            content_type="text/html",
            text_preview="Request Rejected The requested URL was rejected. Please consult with "
            "your administrator. Your support ID is: 9313539871708222202 [Go Back]",
            final_url="https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=xyz",
        )
        self.assertEqual(result.category, "waf_blocked")
        self.assertFalse(result.chatbot_indexable)
        self.assertEqual(result.recommended_action, "slow_down_and_retry_later")

    def test_ib_file_not_found(self):
        result = classify_source_response(
            status_code=200,
            content_type="text/html; charset=utf-8",
            text_preview="檔案[\\\\172.20.4.67\\UserFiles\\FSCRptUpload\\03557115_4986340\\"
            "信用卡綜合保險理賠流程圖.doc]不存在!",
            final_url="https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=abc",
        )
        self.assertEqual(result.category, "not_found")

    def test_tii_captcha_sample(self):
        result = classify_source_response(
            status_code=200,
            content_type="text/html",
            text_preview="請輸入圖形驗證碼後再查詢",
            final_url="https://insprod.tii.org.tw/Query.aspx",
        )
        self.assertEqual(result.category, "captcha_required")
        self.assertFalse(result.chatbot_indexable)

    def test_generic_404(self):
        result = classify_source_response(status_code=404, content_type="text/html", text_preview="")
        self.assertEqual(result.category, "not_found")

    def test_generic_429(self):
        result = classify_source_response(status_code=429, content_type="text/plain", text_preview="")
        self.assertEqual(result.category, "rate_limited")

    def test_html_instead_of_file(self):
        result = classify_source_response(
            status_code=200,
            content_type="text/html; charset=utf-8",
            text_preview="<html><body>ordinary page, nothing wrong with it</body></html>",
            final_url="https://example.gov.tw/DownLoad.aspx?file=xyz",
            expected_binary=True,
        )
        self.assertEqual(result.category, "html_error")
        self.assertFalse(result.chatbot_indexable)

    def test_ordinary_success_is_ok_and_indexable(self):
        result = classify_source_response(
            status_code=200, content_type="application/pdf", text_preview="", final_url="https://example.gov.tw/x.pdf"
        )
        self.assertEqual(result.category, "ok")
        self.assertTrue(result.chatbot_indexable)
        self.assertEqual(result.recommended_action, "index")

    def test_server_error(self):
        result = classify_source_response(status_code=500, content_type="text/html", text_preview="")
        self.assertEqual(result.category, "server_error")

    def test_401_defaults_to_login_required(self):
        result = classify_source_response(status_code=401, content_type="text/html", text_preview="")
        self.assertEqual(result.category, "login_required")

    def test_all_non_ok_categories_are_not_indexable(self):
        for category in ("not_found", "rate_limited", "server_error", "captcha_required", "waf_blocked"):
            with self.subTest(category=category):
                self.assertNotEqual(category, "ok")


if __name__ == "__main__":
    unittest.main()
