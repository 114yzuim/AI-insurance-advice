"""Tests for the IB WAF-token preflight (download_client) and its classifier.

Run: python scripts/test_ib_waf_preflight.py
"""
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sources" / "ib_disclosure"))

from download_client import download_document  # noqa: E402
from failure_classifier import classify  # noqa: E402

BAD = "https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=AAAAStsylRpodrOp!pc002fBBBB!pc003d"
GOOD = "https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=AAAAbbbbCCCC!pc002fBBBB!pc003d"
WAF_HTML = "Request Rejected The requested URL was rejected. Your support ID is: 1"


class FakeClient:
    def __init__(self, url):
        self.url, self.gets = url, 0

    async def post_event(self, *_a, **_k):
        html = f"<script>window.open('{self.url}')</script>".encode()
        return SimpleNamespace(content=html, content_type="text/html", status_code=200,
                               final_url="x", snapshot_path="snap.html")

    async def get(self, _url):
        self.gets += 1
        return SimpleNamespace(content=b"%PDF-1.4 x", content_type="application/pdf", content_disposition="",
                               final_url=_url, status_code=200, checksum="c", snapshot_path="")


class TestPreflight(unittest.TestCase):
    def test_trigger_token_never_sends_get(self):
        client = FakeClient(BAD)
        result = asyncio.run(download_document(client, "d", "t"))
        self.assertEqual(client.gets, 0)
        self.assertEqual(result.status, "html_error")
        self.assertEqual(classify(result.error_evidence)["category"], "waf_false_positive")

    def test_clean_token_still_downloads(self):
        client = FakeClient(GOOD)
        result = asyncio.run(download_document(client, "d", "t", snapshot_dir=Path(__file__).parent / "_tmp_dl"))
        self.assertEqual(client.gets, 1)
        self.assertEqual(result.status, "downloaded")


class TestClassifier(unittest.TestCase):
    def test_old_waf_row_with_trigger_token_reclassified(self):
        ev = {"final_url": BAD, "status_code": 200, "content_type": "text/html", "text_sample": WAF_HTML, "title": "Request Rejected"}
        self.assertEqual(classify(ev)["category"], "waf_false_positive")

    def test_waf_with_clean_token_stays_waf_blocked(self):
        ev = {"final_url": GOOD, "status_code": 200, "content_type": "text/html", "text_sample": WAF_HTML, "title": "Request Rejected"}
        self.assertEqual(classify(ev)["category"], "waf_blocked")

    def test_trigger_token_but_file_not_found_page_not_misclassified(self):
        ev = {"final_url": BAD, "status_code": 200, "content_type": "text/html", "text_sample": "檔案[x.doc]不存在!", "title": ""}
        self.assertEqual(classify(ev)["category"], "source_not_found")


if __name__ == "__main__":
    unittest.main()
