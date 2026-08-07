# Retirement Planning — 5-Module Handoff Bundle

A curated, **reference/assembly** bundle: five self-contained modules sliced from
a working **React/TSX + Python/FastAPI + PostgreSQL** retirement-planning app, for
a classmate to integrate into their own system of the same stack. Every file here
is copied (or sliced) from the live app; the value is in the per-module READMEs
that explain what to rewire.

> This is a reference bundle, not a runnable project. Copied code keeps its
> original imports (e.g. `from app.db import get_connection`,
> `from '../../shared/types'`). The READMEs tell you which cross-module / app
> dependencies to repoint — don't expect imports to resolve standalone.

## The 5 modules

1. **01-client-data** — the client (customer) record + a financials rollup; the
   root entity everything else keys off (`client_id`). Tables: `users`, `clients`,
   `client_financials`.
2. **02-balance-sheet** — per-client asset/liability statement (JSONB) + derived
   summary; writing it syncs the financials rollup. Table: `client_balance_sheet`.
3. **03-questionnaire** — retirement questionnaire (dreams, target, coverage
   flags, consent). Table: `client_questionnaires`.
4. **04-allocation** — the pre-packaged 自由配 / 設定配 (free / constrained)
   allocation engine: `ClientInputs` → an A/B/C split summing to 100%. Pure
   compute, **no DB**. (Already self-documented; see its `README.md` / `contract.md`.)
5. **05-trend-chart** — product-agnostic projection engine + SVG asset-timeline.
   Turns an allocation into one blended rate → a `/forward` projection → a curve.
   No new table (reads 01's tables).

## Shared prerequisites

- **Frontend:** React 18+, TypeScript. Pages also use `react-router-dom`,
  `lucide-react`, and Tailwind utility classes; the chart/allocation use CSS
  variables for theming. A small `api` fetch helper is assumed (not bundled).
- **Backend:** Python 3.12, FastAPI, **pydantic v2** (`pydantic-settings` for the
  config object). DB access via `psycopg2` in the source app.
- **Database:** PostgreSQL. Each DB-backed module ships `schema.sql` then
  `seed.sql`; apply in module order so foreign keys resolve.

## Recommended integration order

```
01-client-data                         (root tables — do first)
  ├─ 02-balance-sheet                  (FK → clients; syncs client_financials)
  └─ 03-questionnaire                  (FK → clients; nudges client_financials)
04-allocation                          (consumes client + questionnaire fields)
05-trend-chart                         (allocation → blended rate → forward → chart)
```

Per module, apply SQL as:
```bash
psql "$DATABASE_URL" -f 01-client-data/schema.sql
psql "$DATABASE_URL" -f 01-client-data/seed.sql
# …then 02, 03 (04 has no DB; 05 reuses 01's tables)
```

## Shared backend dependency note (read before wiring backends)

All DB-touching routers import:
```python
from app.db import get_connection
```
`get_connection()` is a thin context manager over a `psycopg2` connection pool
that yields a connection whose `.cursor()` returns a `RealDictCursor` (rows as
dicts) and which exposes a `.transaction()` helper. **Swap this import for your
own DB accessor.** All SQL in the bundle is **parameterized** (`%s` placeholders);
there are no string-formatted values and no silent fallbacks (a dead DB returns
HTTP 500, it does not fake success).

Config (`database_url`, etc.) comes from `app.core.settings` (a
`pydantic-settings` `BaseSettings`); replace with your own settings object.

Module 04 is the exception: it has **no** `app.db` dependency (pure compute).

## How the modules compose (the integration insight)

`StudioData` in the source app threads them together: the live **client (01)** +
**questionnaire (03)** are mapped to allocation `ClientInputs` (via a
`toClientInputs` adapter), **04-allocation** produces an `a/b/c` split, and
**05-trend-chart** blends that split into one annual rate
`(a·rateA + b·rateB + c·rateC)/100`, POSTs it to `/api/simulator/{id}/forward`,
and renders the returned `yearly_assets` with `<AccumulationChart>`. The full
~25-line wiring snippet is quoted in `05-trend-chart/README.md`.

## What's intentionally NOT here

No `.env` / secrets, no meeting PDFs, no broker-internal files. Just the five
modules' source + schema + mock seed + docs.
