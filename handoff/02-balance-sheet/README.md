# 02 · Balance Sheet

Personal asset/liability statement for a client, stored as two JSONB blobs plus
derived summary numbers. Writing a balance sheet also syncs the client's
`client_financials` rollup (01-client-data), so integrate this after 01.

## Database

Table (see `schema.sql`): `client_balance_sheet` (one row per client, UNIQUE
`client_id`). `assets` and `liabilities` are JSONB; the rest are derived totals.

Apply order (needs `clients` from 01 to exist for the FK):
```bash
psql "$DATABASE_URL" -f schema.sql
psql "$DATABASE_URL" -f seed.sql     # 5 sample rows (clients 1-5)
```

> JSONB shape caveat: `seed.sql` uses the source DB's stored detail keys
> (`assets.cash/investment/property/other/income`, `liabilities.fixed_debts[]/general`),
> while `frontend/types.ts` uses an evolved layout
> (`real_estate/movable/revolving`, `liabilities.fixed{}` keyed map).
> `compute_summary()` tolerates both (it sums numeric leaves and reads
> `liabilities.fixed.*` / `.general.*`). Pick one layout end-to-end for new data.

## Backend (`backend/router.py`, `backend/balance_sheet_utils.py`)

Mount under the `/api/clients` prefix (paths are nested under a client id):
```python
from router import router as balance_router          # adapt import path
app.include_router(balance_router, prefix="/api/clients", tags=["balance-sheet"])
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/clients/{id}/balance-sheet` | — | the stored row, or `null` if none |
| POST | `/api/clients/{id}/balance-sheet` | `{assets, liabilities}` | `{message, summary}`; upserts the row and syncs `client_financials` |

`balance_sheet_utils.py` is pure (no DB/IO) and holds the math:
- `compute_summary(assets, liabilities)` → totals + monthly income/expense/balance
  (used by the endpoint to fill the derived columns).
- `compute_liquid_assets`, `compute_asset_allocation`, `compute_post_plan_allocation`
  — extra helpers for downstream views (donut allocation, retirement-gap inputs).

## Frontend (`frontend/`)

- `BalanceSheet.tsx` — the editor page; `GET`s on load, `POST`s on save.
- `BalanceSheet.constants.ts` — section/field definitions + `emptyAssets` /
  `emptyLiabilities` initial state.
- `types.ts` — `BalanceSheetAssets`, `BalanceSheetLiabilities`, `FixedDebtSlot`
  (sliced from `shared/types.ts`). `BalanceSheet.tsx` also imports `Client`
  (reuse 01-client-data's `Client`).

## Integration notes (what to rewire)

- **Backend DB:** `router.py` imports `from app.db import get_connection`
  (parameterized SQL). The router-local `sync_financials()` writes the
  `client_financials` rollup — drop it if you don't use 01's financials table.
- **Service import:** `router.py` does
  `from app.services.balance_sheet_utils import compute_summary` — repoint to the
  bundled `balance_sheet_utils.py`.
- **Frontend deps not bundled:** `api`, `TopBar`, `ChatPanel`, `formatTwd`,
  `react-router-dom`, `lucide-react`.
