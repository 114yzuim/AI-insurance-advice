# inventory_migrations

Ordered, one-way SQL migrations for `insurance_inventory.db`, applied by
`inventory_db.run_migrations()`.

## Rules

- File name: `NNNN_short_description.sql`, zero-padded, strictly increasing
  (`0001_baseline.sql`, `0002_market_universe.sql`, ...).
- Every statement should be idempotent where practical
  (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`). SQLite has no
  `ADD COLUMN IF NOT EXISTS`, so guard conditional column adds in Python
  instead of SQL if a later migration needs one.
- Migrations only ever move forward. Do not edit a migration that has already
  shipped -- add a new one instead, even to fix a mistake in an earlier file.
- Applied migrations are tracked in the `schema_migrations` table
  (`version` = file stem, e.g. `0001_baseline`). A fresh database and an
  existing production database converge to the same schema because `0001`
  re-states the pre-migration schema with `IF NOT EXISTS` guards.

## Adding a migration

1. Create the next-numbered `.sql` file here.
2. Run the backend once locally (or call `inventory_db.init_inventory_db()`)
   to apply it and confirm it's idempotent by running it twice.
3. Commit the migration file alongside the code that depends on the new
   schema.
