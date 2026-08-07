# 03 · Questionnaire

Retirement-planning questionnaire for a client (channels, dreams, target amount,
existing-coverage flags, consent). Saving it also nudges a couple of
`client_financials` fields and advances client status, so integrate after 01.

## Database

Table (see `schema.sql`): `client_questionnaires` (one row per client, UNIQUE
`client_id`). Mix of JSONB list columns, numerics, and boolean coverage flags.

Apply order (needs `clients` from 01 for the FK):
```bash
psql "$DATABASE_URL" -f schema.sql
psql "$DATABASE_URL" -f seed.sql     # 2 illustrative rows (clients 1-2)
```

> Seed note: the source DB seeds questionnaires for clients 21-50; since this
> bundle's 01 seed only has clients 1-8, `seed.sql` here is two MOCK rows
> re-keyed to clients 1-2, covering every column the PUT endpoint reads.

## Backend (`backend/router.py`)

Mount under the `/api/questionnaires` prefix:
```python
from router import router as questionnaire_router    # adapt import path
app.include_router(questionnaire_router, prefix="/api/questionnaires", tags=["questionnaires"])
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/questionnaires/{id}` | — | the stored row, or `null` if none |
| PUT | `/api/questionnaires/{id}` | questionnaire payload (`dict`, see below) | `{message}`; upserts the row |

The PUT body is a plain object (not a strict pydantic model) — keys mirror the
columns: `preferred_channels`, `retire_income_sources`, `retire_dreams`,
`retire_target_amount`, `retire_monthly_living`, `interested_topics`,
`monthly_investable_budget`, `risk_factors`, `consent_advisory`,
`has_existing_insurance`, `existing_policies_notes`, `health_status`,
`has_family_disease`, `existing_medical_coverage`, `existing_ltc_coverage`, and
the five `has_existing_*` boolean flags.

Side effects inside the same transaction:
- if `monthly_investable_budget > 0` → upserts `client_financials.monthly_investable`.
- if `retire_monthly_living > 0` → updates `client_financials.target_retire_monthly_expense`.
- bumps `clients.status` from `'new'` → `'questionnaire_done'`.

## Frontend (`frontend/`)

- `QuestionnaireForm.tsx` — the form page; `GET`s on load, `PUT`s on save.
- `types.ts` — `Questionnaire` (sliced from `shared/types.ts`).
  The page also imports `Client` (reuse 01-client-data's `Client`).

## Integration notes (what to rewire)

- **Backend DB:** `from app.db import get_connection` (parameterized SQL,
  transactional upsert). The `client_financials` / `clients.status` writes assume
  01-client-data's tables — drop them if you don't use that module.
- **Frontend deps not bundled:** `api`, `TopBar`, `ChatPanel`,
  `react-router-dom`, `lucide-react`.
