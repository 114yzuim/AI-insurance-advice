"""Tests for scripts/object_storage.py.

Run: python scripts/test_object_storage.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from object_storage import FileObjectStore, document_key  # noqa: E402


class TestFileObjectStore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="object_store_test_"))
        self.store = FileObjectStore(self.tmp_dir, bucket="test")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_put_and_get_bytes(self):
        ref = self.store.put_bytes("sources/ib_disclosure/documents/ab/ab12.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        self.assertEqual(ref.scheme, "file")
        self.assertEqual(ref.bucket, "test")
        self.assertEqual(ref.size_bytes, len(b"%PDF-1.4 fake"))
        self.assertEqual(self.store.get_bytes("sources/ib_disclosure/documents/ab/ab12.pdf"), b"%PDF-1.4 fake")
        self.assertTrue(self.store.exists("sources/ib_disclosure/documents/ab/ab12.pdf"))

    def test_content_type_preserved_on_ref(self):
        ref = self.store.put_bytes("x/y.pdf", b"data", content_type="application/pdf")
        self.assertEqual(ref.content_type, "application/pdf")

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put_bytes("../../etc/passwd", b"data")
        with self.assertRaises(ValueError):
            self.store.put_bytes("a/../../b", b"data")
        with self.assertRaises(ValueError):
            self.store.get_bytes("../outside.txt")

    def test_absolute_path_key_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put_bytes("/etc/passwd", b"data")

    def test_duplicate_checksum_idempotent_no_rewrite(self):
        key = document_key("ib_disclosure", "a" * 64, ".pdf")
        ref1 = self.store.put_bytes(key, b"same content")
        path = self.store._resolve(key)
        original_mtime = path.stat().st_mtime_ns
        ref2 = self.store.put_bytes(key, b"same content")
        self.assertEqual(ref1.checksum_sha256, ref2.checksum_sha256)
        # File wasn't rewritten -- mtime unchanged (put_bytes skips writing
        # when the destination already exists).
        self.assertEqual(path.stat().st_mtime_ns, original_mtime)

    def test_exists_false_for_missing_key(self):
        self.assertFalse(self.store.exists("nothing/here.pdf"))

    def test_document_key_layout(self):
        key = document_key("ib_disclosure", "abcdef1234", "pdf")
        self.assertEqual(key, "sources/ib_disclosure/documents/ab/abcdef1234.pdf")


if __name__ == "__main__":
    unittest.main()
