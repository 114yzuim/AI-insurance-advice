import gzip
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import inventory_db
from services import product_service


class ProductInventoryTests(unittest.TestCase):
    def test_database_failure_does_not_return_legacy_products(self):
        with patch.object(product_service, "get_inventory_connection", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                product_service.get_products()

    def test_legacy_fallback_is_not_cached_after_inventory_recovers(self):
        product = {"product_id": "current"}
        with patch.object(product_service, "get_inventory_products", side_effect=[[], [product]]):
            self.assertEqual(len(product_service.get_products()), 780)
            self.assertEqual(product_service.get_products(), [product])

    def test_concurrent_first_reads_import_seed_and_close_connections(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "inventory.db"
            seed_path = Path(folder) / "seed.json.gz"
            with gzip.open(seed_path, "wt", encoding="utf-8") as target:
                json.dump({"insurance_products": [
                    {"id": 1, "product_id": "example", "company_name": "Example", "product_name": "Demo"}
                ]}, target)
            with patch.object(inventory_db, "DB_PATH", db_path), patch.object(inventory_db, "SEED_PATH", seed_path):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    inventories = list(pool.map(lambda _: product_service.get_products(), range(4)))
                self.assertTrue(all(len(items) == 1 and items[0]["product_id"] == "example" for items in inventories))
                # Existing inventory is not overwritten on subsequent init.
                with inventory_db.get_inventory_connection() as conn:
                    conn.execute("UPDATE insurance_products SET product_name = 'Updated'")
                self.assertEqual(product_service.get_products()[0]["product_name"], "Updated")


if __name__ == "__main__":
    unittest.main()
