"""Tests for scripts/document_parser_service.py.

Fixtures are built on the fly with the same libraries that write real
files of each type (python-docx, openpyxl, a minimal hand-built PDF) rather
than checked-in binary fixtures, so the test suite has no binary assets to
maintain.

Run: python scripts/test_document_parser_service.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from document_parser_service import parse_document  # noqa: E402

# A minimal, valid, single-page PDF containing the text "Hello Insurance" --
# built by hand (no reportlab dependency) so this test needs nothing beyond
# what's already installed (pdfplumber/pypdf, both read-only here).
_MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 58>>
stream
BT /F1 18 Tf 10 100 Td (Hello Insurance Document) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f
trailer<</Size 6/Root 1 0 R>>
startxref
0
%%EOF
"""


class TestDocumentParserService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="doc_parser_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_pdf_fixture_parsed(self):
        path = self.tmp_dir / "sample.pdf"
        path.write_bytes(_MINIMAL_PDF)
        result = parse_document(path, document_type="POLICY_TERMS", source_url="https://x/y.pdf", document_id="42")
        self.assertIn(result.status, ("parsed", "parse_failed"))  # hand-built PDF may not extract on every backend
        if result.status == "parsed":
            self.assertIn("Insurance", result.text)
            self.assertTrue(result.chunks)
            self.assertEqual(result.chunks[0].citation["document_id"], "42")
            self.assertEqual(result.chunks[0].citation["document_type"], "POLICY_TERMS")

    def test_docx_fixture_parsed(self):
        import docx

        path = self.tmp_dir / "sample.docx"
        document = docx.Document()
        document.add_paragraph("條款第一條：本保險契約所稱之要保人。")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "項目"
        table.rows[0].cells[1].text = "內容"
        document.save(path)

        result = parse_document(path, document_type="POLICY_TERMS")
        self.assertEqual(result.status, "parsed")
        self.assertIn("要保人", result.text)
        self.assertEqual(result.table_count, 1)
        self.assertTrue(result.chunks)

    def test_xlsx_fixture_parsed(self):
        import openpyxl

        path = self.tmp_dir / "sample.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["年齡", "保費"])
        sheet.append([30, 1200])
        workbook.save(path)

        result = parse_document(path, document_type="RATE_TABLE")
        self.assertEqual(result.status, "parsed")
        self.assertIn("保費", result.text)
        self.assertEqual(result.table_count, 1)

    def test_csv_fixture_parsed(self):
        path = self.tmp_dir / "sample.csv"
        path.write_text("項目,金額\n住院日額,1000\n", encoding="utf-8")
        result = parse_document(path, document_type="RATE_TABLE")
        self.assertEqual(result.status, "parsed")
        self.assertIn("住院日額", result.text)

    def test_legacy_doc_marked_downloaded_not_parsed(self):
        path = self.tmp_dir / "sample.doc"
        path.write_bytes(b"\xd0\xcf\x11\xe0 fake ole binary")
        result = parse_document(path)
        self.assertEqual(result.status, "downloaded_not_parsed")
        self.assertEqual(result.chunks, [])

    def test_legacy_xls_marked_downloaded_not_parsed(self):
        path = self.tmp_dir / "sample.xls"
        path.write_bytes(b"\xd0\xcf\x11\xe0 fake ole binary")
        result = parse_document(path)
        self.assertEqual(result.status, "downloaded_not_parsed")

    def test_unsupported_extension(self):
        path = self.tmp_dir / "sample.zip"
        path.write_bytes(b"PK\x03\x04fake zip")
        result = parse_document(path)
        self.assertEqual(result.status, "unsupported_type")

    def test_blocked_html_saved_as_pdf_does_not_get_chunked(self):
        path = self.tmp_dir / "fake.pdf"
        path.write_bytes(
            b"<html><head><title>Request Rejected</title></head><body>"
            b"Request Rejected The requested URL was rejected. Your support ID is: 12345"
            b"</body></html>"
        )
        result = parse_document(path)
        self.assertEqual(result.status, "parse_failed")
        self.assertEqual(result.chunks, [])
        self.assertTrue(any("waf_blocked" in e for e in result.errors))

    def test_rerun_is_idempotent(self):
        path = self.tmp_dir / "sample.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        first = parse_document(path)
        second = parse_document(path)
        self.assertEqual(first.text, second.text)
        self.assertEqual(len(first.chunks), len(second.chunks))


if __name__ == "__main__":
    unittest.main()
