"""Tests for scripts/parse_document_snapshots.py's dispatch + dry-run
behavior (not the full DB-backed CLI -- that's exercised live against the
real inventory DB, see docs/production_deployment_readiness.md's staging
checklist).

Run: python scripts/test_parse_document_snapshots.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parse_document_snapshots  # noqa: E402


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        max_pages=200, max_bytes=20_000_000, chunk_size=1800, chunk_overlap=180,
        enable_windows_com=False, dry_run=True,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestParseDocumentSnapshotsDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="parse_doc_snapshots_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _document(self, filename: str) -> dict:
        path = self.tmp_dir / filename
        path.write_text("項目,金額\n住院日額,1000\n", encoding="utf-8") if filename.endswith(".csv") else path.write_bytes(b"x")
        return {
            "document_id": 1,
            "product_db_id": 1,
            "local_path": str(path.relative_to(parse_document_snapshots.ROOT)) if path.is_relative_to(parse_document_snapshots.ROOT) else str(path),
            "document_type": "RATE_TABLE",
            "pdf_url": "",
        }

    def test_dry_run_never_calls_save_parse(self):
        document = self._document("sample.csv")
        with patch.object(parse_document_snapshots, "save_parse") as mock_save:
            parse_document_snapshots.parse_one(document, _args(dry_run=True))
            mock_save.assert_not_called()

    def test_non_dry_run_calls_save_parse(self):
        document = self._document("sample.csv")
        with patch.object(parse_document_snapshots, "save_parse") as mock_save:
            parse_document_snapshots.parse_one(document, _args(dry_run=False))
            mock_save.assert_called_once()

    def test_unsupported_legacy_extension_routed_correctly(self):
        document = self._document("sample.ppt")
        with patch.object(parse_document_snapshots, "save_parse"):
            result = parse_document_snapshots.parse_one(document, _args(dry_run=True))
        self.assertEqual(result["status"], "unsupported_legacy_format")

    def test_doc_extension_routes_to_legacy_office_parser(self):
        document = self._document("sample.doc")
        with patch.object(parse_document_snapshots, "save_parse"), patch(
            "parse_document_snapshots.parse_doc"
        ) as mock_parse_doc:
            from document_parser_service import DocumentParseResult

            mock_parse_doc.return_value = DocumentParseResult(status="parser_unavailable", parser_name="stub")
            result = parse_document_snapshots.parse_one(document, _args(dry_run=True))
        mock_parse_doc.assert_called_once()
        self.assertEqual(result["status"], "parser_unavailable")

    def test_xls_extension_routes_to_legacy_office_parser(self):
        document = self._document("sample.xls")
        with patch.object(parse_document_snapshots, "save_parse"), patch(
            "parse_document_snapshots.parse_xls"
        ) as mock_parse_xls:
            from document_parser_service import DocumentParseResult

            mock_parse_xls.return_value = DocumentParseResult(status="parsed", parser_name="stub", text="x")
            parse_document_snapshots.parse_one(document, _args(dry_run=True))
        mock_parse_xls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
