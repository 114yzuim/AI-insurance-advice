"""Tests for scripts/legacy_office_parser.py.

Needs `xlwt` (pip install xlwt) to WRITE a .xls fixture -- test-only, NOT
added to backend/requirements.txt (xlrd, the thing this module actually
uses to READ .xls in production, already is).

This machine has no LibreOffice installed (verified live 2026-09-14 --
`shutil.which("soffice")`/`shutil.which("libreoffice")` both return None),
which is exactly the "LibreOffice not found" case Task 1 asked to be
tested -- so that test exercises the real absence, not a mock. The
blocked-HTML-as-.doc test needs a parser that actually RUNS to prove it
rejects the content (not just "unavailable"), so it uses
--enable-windows-com (pywin32 IS available on this machine) rather than
LibreOffice.

Run: python scripts/test_legacy_office_parser.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import legacy_office_parser  # noqa: E402
from legacy_office_parser import parse_doc, parse_xls  # noqa: E402


class TestParseXls(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="legacy_office_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_xls_fixture_parsed(self):
        import xlwt

        path = self.tmp_dir / "sample.xls"
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("費率表")
        sheet.write(0, 0, "年齡")
        sheet.write(0, 1, "保費")
        sheet.write(1, 0, 30)
        sheet.write(1, 1, 1200)
        workbook.save(str(path))

        result = parse_xls(path, document_type="RATE_TABLE")
        self.assertEqual(result.status, "parsed")
        self.assertIn("保費", result.text)
        self.assertEqual(result.table_count, 1)
        self.assertTrue(result.chunks)
        self.assertEqual(result.chunks[0].citation["document_type"], "RATE_TABLE")

    def test_xls_blocked_html_not_parsed(self):
        path = self.tmp_dir / "fake.xls"
        path.write_bytes(
            b"<html><head><title>Request Rejected</title></head><body>"
            b"Request Rejected The requested URL was rejected. Your support ID is: 999"
            b"</body></html>"
        )
        result = parse_xls(path)
        self.assertEqual(result.status, "parse_failed")
        self.assertEqual(result.chunks, [])

    def test_xls_malformed_file_parse_failed_not_crash(self):
        path = self.tmp_dir / "garbage.xls"
        path.write_bytes(b"not a real xls file at all, just garbage bytes")
        result = parse_xls(path)
        self.assertEqual(result.status, "parse_failed")


class TestParseDoc(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="legacy_office_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_libreoffice_not_found_is_parser_unavailable(self):
        # This machine (a bare Windows dev box) genuinely has no LibreOffice
        # on PATH -- see module docstring. Verified live 2026-09-18 that
        # the real Dockerfile.worker container DOES have it (that's the
        # whole point), so this test is skipped there rather than forced to
        # fail: it specifically exercises the "not found" branch, which
        # only exists on a machine without LibreOffice.
        if legacy_office_parser.libreoffice_available():
            self.skipTest("LibreOffice is available on this machine -- see test_libreoffice_used_when_available instead")
        path = self.tmp_dir / "sample.doc"
        path.write_bytes(b"\xd0\xcf\x11\xe0 fake ole binary")
        result = parse_doc(path, enable_windows_com=False)
        self.assertEqual(result.status, "parser_unavailable")
        self.assertEqual(result.chunks, [])
        self.assertTrue(any("LibreOffice" in w or "--enable-windows-com" in w for w in result.warnings))

    def test_com_not_used_without_opt_in(self):
        """parse_doc() without enable_windows_com must never touch
        pywin32/Word, proven by the parser_name never being the COM one --
        regardless of whether LibreOffice happens to be installed on this
        machine (if it is, LibreOffice legitimately parses it and that's a
        real 'parsed' result via a DIFFERENT parser, not a violation of
        this test's point).
        """
        path = self.tmp_dir / "sample.doc"
        path.write_bytes(b"\xd0\xcf\x11\xe0 fake ole binary")
        result = parse_doc(path, enable_windows_com=False)
        self.assertNotEqual(result.parser_name, legacy_office_parser.PARSER_NAME_DOC_COM)
        if not legacy_office_parser.libreoffice_available():
            self.assertNotEqual(result.status, "parsed")

    def test_libreoffice_used_when_available(self):
        """The container-side counterpart to test_libreoffice_not_found_is_
        parser_unavailable -- only meaningful (and only run) on a machine
        that actually has LibreOffice, e.g. the real Dockerfile.worker
        image. A malformed fake .doc can't be expected to convert cleanly,
        so this only checks that the LibreOffice code path is the one that
        ran (parser_name), not that it produced real text.
        """
        if not legacy_office_parser.libreoffice_available():
            self.skipTest("LibreOffice is not available on this machine -- see test_libreoffice_not_found_is_parser_unavailable instead")
        path = self.tmp_dir / "sample.doc"
        path.write_bytes(b"\xd0\xcf\x11\xe0 fake ole binary")
        result = parse_doc(path, enable_windows_com=False)
        self.assertEqual(result.parser_name, legacy_office_parser.PARSER_NAME_DOC_LIBREOFFICE)

    def test_blocked_html_as_doc_via_com_is_parse_failed(self):
        path = self.tmp_dir / "fake.doc"
        path.write_bytes(
            b"<html><head><title>Request Rejected</title></head><body>"
            b"Request Rejected The requested URL was rejected. Your support ID is: 999"
            b"</body></html>"
        )
        result = parse_doc(path, enable_windows_com=True)
        self.assertEqual(result.status, "parse_failed")
        self.assertEqual(result.chunks, [])
        self.assertTrue(any("waf_blocked" in e for e in result.errors))

    def test_com_fallback_parses_real_doc_when_opted_in(self):
        """Real end-to-end signal (not just 'doesn't crash') that the COM
        fallback still works when LibreOffice is unavailable and the caller
        opts in -- uses a real .doc fixture built via win32com itself
        (the same mechanism the parser uses), skipped if that's not
        possible in this environment.
        """
        try:
            import win32com.client
        except ImportError:
            self.skipTest("pywin32 not available")

        path = self.tmp_dir / "sample.doc"
        word = None
        document = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            document = word.Documents.Add()
            document.Content.Text = "條款第一條：本保險契約所稱之要保人，指對保險標的具有保險利益。"
            document.SaveAs(str(path.resolve()), FileFormat=0)  # wdFormatDocument (.doc)
        except Exception as exc:  # noqa: BLE001 -- environment-dependent, not this module's own bug
            self.skipTest(f"could not build a real .doc fixture via COM: {exc}")
        finally:
            if document is not None:
                document.Close(False)
            if word is not None:
                word.Quit()

        result = parse_doc(path, document_type="POLICY_TERMS", enable_windows_com=True)
        self.assertEqual(result.status, "parsed")
        self.assertIn("要保人", result.text)
        self.assertTrue(result.chunks)
        self.assertEqual(result.chunks[0].citation["document_type"], "POLICY_TERMS")


if __name__ == "__main__":
    unittest.main()
