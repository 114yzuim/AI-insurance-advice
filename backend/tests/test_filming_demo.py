import sqlite3
import unittest
from pathlib import Path

import inventory_db
from services.policy_service import policy_to_dict


BACKEND = Path(__file__).resolve().parents[1]
MIGRATION = "0009_xiao_an_filming_demo.sql"


class FilmingDemoTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(inventory_db._SCHEMA)
        self.addCleanup(self.conn.close)

    def demo_policy(self):
        return self.conn.execute(
            "SELECT * FROM customer_policies WHERE profile_id = ?",
            ("cardif-xiao-an-demo",),
        ).fetchone()

    def test_migration_creates_usable_demo_and_is_recorded_once(self):
        inventory_db.run_migrations(self.conn)
        inventory_db.run_migrations(self.conn)
        profile = self.conn.execute(
            "SELECT * FROM insurance_profiles WHERE id = 'cardif-xiao-an-demo'"
        ).fetchone()
        self.assertEqual(profile["owner_name"], "小安（示範）")
        policy = policy_to_dict(self.conn, self.demo_policy())
        self.assertEqual(policy["policy_no"], "DEMO-XA-2026-001")
        self.assertEqual(policy["coverages"], {"daily": 2000, "medical": 20})
        self.assertEqual(policy["completeness"]["score"], 89)
        self.assertEqual(policy["completeness"]["missing"], [
            {"key": "terms_source", "label": "條款 / 來源商品"}
        ])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM customer_policies").fetchone()[0], 1)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (Path(MIGRATION).stem,)
        ).fetchone()[0], 1)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_rerun_preserves_existing_policies_and_user_edits(self):
        sql = (BACKEND / "inventory_migrations" / MIGRATION).read_text(encoding="utf-8")
        self.conn.execute("INSERT INTO insurance_profiles (id, owner_name) VALUES ('existing', 'Existing owner')")
        self.conn.execute("INSERT INTO customer_policies (profile_id, company_name, policy_name) VALUES ('existing', 'Existing company', 'Existing policy')")
        self.conn.executescript(sql)
        policy_id = self.demo_policy()["id"]
        self.conn.execute("UPDATE insurance_profiles SET owner_name = 'Edited owner' WHERE id = 'cardif-xiao-an-demo'")
        self.conn.execute("UPDATE customer_policies SET annual_premium = 12345 WHERE id = ?", (policy_id,))
        self.conn.execute("UPDATE customer_policy_coverages SET amount = 3000 WHERE policy_id = ? AND coverage_key = 'daily'", (policy_id,))
        self.conn.executescript(sql)
        self.assertEqual(self.demo_policy()["annual_premium"], 12345)
        self.assertEqual(policy_to_dict(self.conn, self.demo_policy())["coverages"]["daily"], 3000)
        self.assertEqual(self.conn.execute("SELECT owner_name FROM insurance_profiles WHERE id = 'cardif-xiao-an-demo'").fetchone()[0], "Edited owner")
        self.assertEqual(self.conn.execute("SELECT policy_name FROM customer_policies WHERE profile_id = 'existing'").fetchone()[0], "Existing policy")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM customer_policies").fetchone()[0], 2)

    def test_postgres_seed_contains_the_same_synthetic_data(self):
        # Both engines support this INSERT/SELECT/ON CONFLICT subset.
        self.assertEqual(
            (BACKEND / "inventory_migrations" / MIGRATION).read_text(encoding="utf-8"),
            (BACKEND / "inventory_migrations_pg" / MIGRATION).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
