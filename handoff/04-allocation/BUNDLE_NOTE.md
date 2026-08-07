# 04 · Allocation — bundle note

This folder is the **pre-packaged 自由配 / 設定配 (free / constrained allocation)
module**, copied intact from the source repo's `O/handoff-allocation/`. It is
already self-documented — read these in order:

- `README.md` — what it is, how to mount the router / call the pure functions,
  frontend wiring, customization points, scope.
- `contract.md` — the full API contract (`/estimate`, `/solve`) with request /
  response JSON (camelCase) and constraint semantics.
- `DESIGN.md` — design spec and the decisions behind the two-layer model
  (individual needs → 100% allocation).

## What's inside

```
backend/
  allocation/   models.py · estimator.py · solver.py · router.py · __init__.py
  tests/        test_estimator.py · test_solver.py   (pytest, all green)
  conftest.py · requirements.txt
frontend/
  AllocationStrategy.tsx · StrategyModeCards.tsx · ConstraintEditor.tsx
  AllocationResult.tsx · api.ts · types.ts · styles.css · tsconfig.json
```

## Endpoints (summary — see `contract.md` for full shapes)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/allocation/estimate` | 自由配: `ClientInputs` → `{needs, allocation}` (allocation sums to 100) |
| POST | `/api/allocation/solve` | 設定配: `{client \| baseline, constraints[]}` → `AllocationResult` (constraint-aware, infeasibility flagged at HTTP 200) |

## Self-contained?

More than the other modules: the backend depends only on `pydantic` (and
`fastapi` for the router); it has **no `app.db` dependency** — allocation is pure
computation, no SQL. It does, however, consume the same `ClientInputs` fields
that 01-client-data + 03-questionnaire produce (age, retireAge, dependents,
riskTolerance, coverage flags). In the source app, `StudioData` derives
`ClientInputs` from the live client + questionnaire (see the top-level README's
`toClientInputs` reference) and feeds `allocation` into 05-trend-chart.
