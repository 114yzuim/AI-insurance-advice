# 05 · Trend Chart (asset-projection timeline)

A product-agnostic retirement projection engine + an SVG timeline that renders
the resulting asset curve (accumulation before retirement, drawdown after).
This is where 04-allocation's output becomes a single real curve — see the
**wiring pattern** below; that's the key integration insight of the whole bundle.

No new DB table: the engine reads a client's ages + financials from
01-client-data's `clients` / `client_financials`.

## Backend (`backend/router.py`, `backend/simulator/`)

`simulator/` is a pure compounding engine (no DB):
- `core.py` — `simulate_forward` (savings plan → future value, withdrawable
  income, achievement ratio, and a year-by-year `yearly_assets` path),
  `simulate_reverse_to_saving`, `simulate_reverse_to_rate` (bisection).
- `constants.py` — neutral defaults (default rate 6%, inflation 2.5%, rate
  bounds, post-retirement factor) + category rates used for the blended rate.
- `strategy.py` — per-module A/B/C category-level projections
  (`compare_allocations`); carries `estimation_type: "category_level"`.
- `__init__.py` — re-exports.

`router.py` mounts under `/api/simulator` and merges payload overrides with DB
defaults via `_resolve_ages_and_assets()` (this is the only DB-touching part):
```python
from router import router as simulator_router        # adapt import path
app.include_router(simulator_router, prefix="/api/simulator", tags=["simulator"])
```

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/simulator/{id}/defaults` | — | pre-filled inputs + `category_rates`, `assumptions`, `disclaimer` |
| POST | `/api/simulator/{id}/forward` | overrides incl. `annual_rate`, `inflation_rate` | `{inputs, result, assumptions, disclaimer}` — `result.yearly_assets` is the curve |
| POST | `/api/simulator/{id}/reverse-saving` | target (`monthly`/`corpus`) | required monthly saving |
| POST | `/api/simulator/{id}/reverse-rate` | savings + withdrawal target | required annual rate |

Every money response carries `assumptions` + `disclaimer` (compute-not-advice).

## Frontend (`frontend/`)

- `AccumulationChart.tsx` — the SVG timeline. Props: `data: AccPoint[]`
  (`{y: age, v: 萬}`), optional `data2` for comparison, `retireAge` (marker line),
  `color`, `height`. Renders gridlines, peak dot, and a 退休 marker. Uses CSS
  variables (`--green-600`, `--gold-500`, `--ink-3`, `--line`, `--font-mono`) —
  define them or swap for your own.
- `adapters.ts` — `toAccPoints(yearly)`: maps the engine's `yearly_assets`
  (`assets_twd`, NT$) → `AccPoint[]` (萬, rounded). Extracted from the source
  `src/pages/Studio/data/adapters.ts`.
- `types.ts` — `AccPoint`.

## Wiring pattern (allocation → blended rate → forward → chart)

This is the load-bearing integration. The allocation result (`a/b/c`, summing to
100) is collapsed into one blended annual rate using each bucket's category rate,
that rate drives a single `/forward` call, and the returned `yearly_assets`
becomes the chart's `data`. Quoted from the source `StudioData.tsx`
(the blended-rate + forward effect):

```tsx
// allocation 變動 → blended rate → forward（單一真實時間軸）
const rates = {
  A: defaults.category_rates?.A ?? FALLBACK_RATES.A,   // FALLBACK = {A:0.06, B:0.022, C:0}
  B: defaults.category_rates?.B ?? FALLBACK_RATES.B,
  C: defaults.category_rates?.C ?? FALLBACK_RATES.C,
};
const blendedRate =
  (allocation.a * rates.A + allocation.b * rates.B + allocation.c * rates.C) / 100;
const body: ForwardBody = {
  current_age: defaults.current_age,
  retire_age: defaults.retire_age,
  life_expectancy: defaults.life_expectancy,
  current_assets_twd: defaults.current_assets_twd,
  monthly_saving_twd: defaults.monthly_saving_twd,
  target_monthly_expense_twd: defaults.target_monthly_expense_twd,
  annual_rate: blendedRate,
  inflation_rate: defaults.inflation_rate,
};
const r = await api.post<{ result: ForwardResult }>(
  `/api/simulator/${clientId}/forward`,
  body,
);
setForward(r.result);                                  // r.result.yearly_assets
// then: const accPoints = toAccPoints(forward.yearly_assets);
//       <AccumulationChart data={accPoints} retireAge={defaults.retire_age} />
```

Flow in one line:
`allocation (04) → blendedRate = (a·rA + b·rB + c·rC)/100 → POST /forward {annual_rate: blendedRate} → result.yearly_assets → toAccPoints → <AccumulationChart>`.

## Integration notes (what to rewire)

- **Backend DB:** `router.py` imports `from app.db import get_connection` and
  `from app.services.simulator import ...` — repoint the latter to the bundled
  `simulator/` package. `_resolve_ages_and_assets()` is the only DB read
  (parameterized); the engine itself is pure.
- **Frontend deps not bundled:** the `api` helper, and the CSS variables the
  chart uses. `defaults.category_rates` come from `GET /api/simulator/{id}/defaults`.
