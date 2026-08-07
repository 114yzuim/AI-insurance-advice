# 01 · Client Data

CRUD for the customer (client) record + a rollup financials row. This is the
root entity every other module points at via `client_id`, so integrate it first.

## Database

Tables (see `schema.sql`): `users`, `clients`, `client_financials`.

- `users` — brokers. The source app hardcodes a single broker (`id = 1`).
- `clients` — the customer. Includes joint-plan (spouse) fields and
  `selected_modules TEXT[]` (`A`=投資 / `B`=保險 / `C`=失能長照).
- `client_financials` — one row per client (UNIQUE `client_id`), rollup numbers
  the list/detail endpoints LEFT JOIN onto the client.

Apply order:
```bash
psql "$DATABASE_URL" -f schema.sql   # creates the 3 tables + indexes
psql "$DATABASE_URL" -f seed.sql     # 1 broker + 8 sample clients + financials
```

## Backend (`backend/router.py`, `backend/schemas.py`)

FastAPI router. Mount under the `/api/clients` prefix:
```python
from fastapi import FastAPI
from router import router as clients_router          # adapt import path
app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
```

Pydantic v2 request models live in `schemas.py` (`ClientCreate`, `ClientUpdate`;
`ClientUpdate` just subclasses `ClientCreate`).

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/clients` | — (`?include_demo`, `?skip`, `?limit`) | `Client[]`, or `{items,total,skip,limit}` when `limit>0`. Each row carries the joined `client_financials` columns. |
| GET | `/api/clients/{id}` | — | `Client` (404 if missing) |
| POST | `/api/clients` | `ClientCreate` | `{id, message}` (201). Inserts client + financials in one transaction. |
| PUT | `/api/clients/{id}` | `ClientUpdate` | `{message}`. Updates client + upserts financials. |
| DELETE | `/api/clients/{id}` | — | `{message}` (404 if missing; cascades) |

Notes:
- `POST` hardcodes `user_id = 1` (the demo broker). Swap for your auth'd user.
- JSONB columns (`children_ages`, `planning_goals`) are written via
  `psycopg2.extras.Json`.

## Frontend (`frontend/`)

React 18 + TypeScript pages (Notion/Linear-styled, Tailwind classes + lucide-react icons):

- `ClientList.tsx` — roster; fetches `GET /api/clients`.
- `ClientForm.tsx` — create (no id) / edit (`/:id`); `POST` / `PUT`.
- `ClientHub.tsx` — read-only client summary; also reads balance-sheet summary.
- `types.ts` — `Client` + `ModuleCode`, sliced from the app's `shared/types.ts`.

Data source: all three call a small `api` helper (`api.get/post/put`). In the
source repo that's `src/lib/api.ts` (a thin `fetch` wrapper). They also import
`TopBar`, `ChatPanel`, and `src/lib/labels`/`utils` helpers that are NOT in this
bundle — see integration notes.

## Integration notes (what to rewire)

- **Backend DB:** `router.py` imports `from app.db import get_connection` — a
  context manager yielding a pooled psycopg2 connection with a `RealDictCursor`
  and a `.transaction()` helper. Replace with your own accessor. All SQL is
  parameterized (`%s`).
- **Types:** `frontend/types.ts` is the single source of truth for `Client`;
  02/03 reference the same `Client` shape.
- **Frontend deps not bundled:** `api`, `TopBar`, `ChatPanel`, `STATUS_LABEL`,
  `formatTwd`, `react-router-dom`, `lucide-react`. Provide your own or strip the
  imports — the data-fetching logic is the reusable part.
