import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import inventory_db
from services import claim_case_service


class ClaimCaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(inventory_db._SCHEMA)
        self.addCleanup(self.conn.close)

        @contextmanager
        def connection():
            with self.conn:
                yield self.conn

        self.connection_patch = patch.object(claim_case_service, "get_inventory_connection", connection)
        self.profile_patch = patch.object(claim_case_service, "ensure_default_profile")
        self.connection_patch.start()
        self.profile_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.addCleanup(self.profile_patch.stop)

    def test_create_list_update_preserves_document_data_and_profile_scope(self):
        payload = {
            "profile_id": "cardif-xiao-an-demo",
            "owner_name": "小安（示範）",
            "scenario": "合成測試案例",
            "medical_expense_total": 42000,
            "document_summary": {"diagnoses": ["急性闌尾炎"], "hospital_stay": {"days": 4}},
            "required_documents": [{"name": "診斷證明", "count": 1}],
        }
        created = claim_case_service.create_claim_case(payload)
        self.assertIsInstance(created["id"], int)
        self.assertEqual(created["document_summary"], payload["document_summary"])
        self.assertEqual(created["medical_expense_total"], 42000)
        self.assertEqual(claim_case_service.list_claim_cases("cardif-xiao-an-demo"), [created])
        self.assertEqual(claim_case_service.list_claim_cases("another-profile"), [])
        updated = claim_case_service.update_claim_case(created["id"], {"notes": "待確認正式條款", "status": "待送件"})
        self.assertEqual(updated["notes"], "待確認正式條款")
        self.assertEqual(updated["status"], "待送件")
        self.assertEqual(updated["document_summary"], payload["document_summary"])

    def test_iso_timestamps_sort_newest_then_id(self):
        first = claim_case_service.create_claim_case({"profile_id": "test"})
        second = claim_case_service.create_claim_case({"profile_id": "test"})
        self.conn.execute("UPDATE claim_cases SET updated_at = '2026-10-29 09:00:00' WHERE id = ?", (second["id"],))
        self.conn.execute("UPDATE claim_cases SET updated_at = '2026-10-30 09:00:00' WHERE id = ?", (first["id"],))
        self.assertEqual([case["id"] for case in claim_case_service.list_claim_cases("test")], [first["id"], second["id"]])


if __name__ == "__main__":
    unittest.main()
