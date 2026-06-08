"""DB-severed input adapter + thin run wrappers.

WHY this file exists
====================
In the source system the engine was reached through two FastAPI routers
(app/api/routers/simulator.py, strategy.py). The ONLY coupling that stopped the
engine from being portable was ``_resolve_ages_and_assets(client_id, payload)``
in simulator.py (lines ~76-130): it opened a DB connection and ran a
``clients LEFT JOIN client_financials`` query to build the 7 engine inputs.
strategy.py then imported that same function.

This adapter reproduces that resolution logic **without any DB / FastAPI**.
You feed it a plain ``dict`` (from whatever store the new system uses —
PostgreSQL row, JSON, localStorage payload) and it returns engine-ready inputs.
The engine itself (engine/core.py, strategy.py) was NOT modified — its function
signatures already take pure keyword arguments.

WHAT to change when integrating
===============================
- Replace ``resolve_inputs(record, overrides)`` 's record source with your data
  layer (or just hand it a dict you already have).
- The ``run_*`` helpers return the same response shape the original API emitted
  (inputs + result + assumptions + disclaimer) so a frontend ported from the old
  system keeps working.

Pure module — imports only from the engine package + adapter.disclaimers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine import constants as C
from engine import (
    compare_allocations,
    simulate_forward,
    simulate_reverse_to_rate,
    simulate_reverse_to_saving,
)
from adapter.disclaimers import ASSUMPTIONS, DISCLAIMER, strategy_disclaimer

VALID_MODULES = {"A", "B", "C"}


@dataclass
class SimulatorInputs:
    """The exact 7+1 inputs the engine consumes. No DB types leak in here."""

    current_age: int
    retire_age: int
    life_expectancy: int
    current_assets_twd: float
    monthly_saving_twd: float
    target_monthly_expense_twd: float
    selected_modules: list[str] = field(default_factory=lambda: ["A"])

    def as_engine_kwargs(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("selected_modules", None)
        return d


# ── input resolution (replaces the DB query in _resolve_ages_and_assets) ──────

def _pick(record: dict[str, Any], *keys: str) -> Any:
    """First non-None value among keys — mirrors the router's legacy/_twd alias
    handling so both ``current_assets`` and ``current_assets_twd`` work."""
    for k in keys:
        v = record.get(k)
        if v is not None:
            return v
    return None


def resolve_inputs(
    record: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> SimulatorInputs:
    """Build engine inputs from a client record dict + optional UI overrides.

    ``record`` keys (all optional, sensible defaults applied) — these mirror the
    columns the old SQL selected from clients + client_financials:
        age, target_retire_age, life_expectancy,
        is_joint_plan, spouse_age, spouse_life_expectancy, selected_modules,
        current_assets, monthly_investable, target_retire_monthly_expense

    ``overrides`` = what the UI sent (the old ``payload``). Accepts both the
    ``*_twd`` names the frontend sends and the legacy names.
    """
    record = record or {}
    overrides = overrides or {}

    is_joint = bool(record.get("is_joint_plan")) and bool(record.get("spouse_age"))
    default_life = (
        max(
            int(record.get("life_expectancy") or 85),
            int(record.get("spouse_life_expectancy") or 85),
        )
        if is_joint
        else int(record.get("life_expectancy") or 85)
    )
    expense_multiplier = 1.6 if is_joint else 1.0

    assets_override = _pick(overrides, "current_assets_twd", "current_assets")
    saving_override = _pick(overrides, "monthly_saving_twd", "monthly_saving")
    expense_override = _pick(
        overrides, "target_monthly_expense_twd", "target_monthly_expense"
    )

    def coalesce(a: Any, b: Any) -> Any:
        return b if a is None else a

    return SimulatorInputs(
        current_age=int(coalesce(overrides.get("current_age"), record.get("age")) or 35),
        retire_age=int(
            coalesce(overrides.get("retire_age"), record.get("target_retire_age")) or 65
        ),
        life_expectancy=int(
            coalesce(overrides.get("life_expectancy"), default_life) or 85
        ),
        current_assets_twd=float(
            assets_override
            if assets_override is not None
            else (record.get("current_assets") or 0)
        ),
        monthly_saving_twd=float(
            saving_override
            if saving_override is not None
            else (record.get("monthly_investable") or 0)
        ),
        target_monthly_expense_twd=float(
            expense_override
            if expense_override is not None
            else (float(record.get("target_retire_monthly_expense") or 40000) * expense_multiplier)
        ),
        selected_modules=list(record.get("selected_modules") or ["A"]),
    )


# ── run wrappers (mirror the old router responses, minus DB/HTTP) ────────────

def run_forward(
    inputs: SimulatorInputs,
    *,
    annual_rate: float | None = None,
    inflation_rate: float | None = None,
) -> dict[str, Any]:
    """Mode 1: savings plan → future value, withdrawable income, achievement."""
    result = simulate_forward(
        **inputs.as_engine_kwargs(),
        annual_rate=annual_rate if annual_rate is not None else C.DEFAULT_ANNUAL_RATE,
        inflation_rate=inflation_rate if inflation_rate is not None else C.DEFAULT_INFLATION_RATE,
    )
    return {
        "inputs": asdict(inputs),
        "result": asdict(result),
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


def run_reverse_saving(
    inputs: SimulatorInputs,
    *,
    target_kind: str = "monthly",
    target_corpus_twd: float = 0.0,
    annual_rate: float | None = None,
    inflation_rate: float | None = None,
) -> dict[str, Any]:
    """Mode 2: target → required monthly saving. target_kind: 'monthly' | 'corpus'."""
    if target_kind not in ("monthly", "corpus"):
        raise ValueError("target_kind must be 'monthly' or 'corpus'")
    if target_kind == "corpus" and target_corpus_twd <= 0:
        raise ValueError("target_corpus_twd must be > 0 when target_kind = 'corpus'")
    result = simulate_reverse_to_saving(
        current_age=inputs.current_age,
        retire_age=inputs.retire_age,
        life_expectancy=inputs.life_expectancy,
        current_assets_twd=inputs.current_assets_twd,
        target_monthly_expense_twd=inputs.target_monthly_expense_twd,
        target_corpus_twd=target_corpus_twd,
        target_kind=target_kind,
        annual_rate=annual_rate if annual_rate is not None else C.DEFAULT_ANNUAL_RATE,
        inflation_rate=inflation_rate if inflation_rate is not None else C.DEFAULT_INFLATION_RATE,
    )
    return {
        "inputs": asdict(inputs),
        "result": asdict(result),
        "target_kind": target_kind,
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


def run_reverse_rate(
    inputs: SimulatorInputs,
    *,
    inflation_rate: float | None = None,
) -> dict[str, Any]:
    """Mode 3: savings plan + withdrawal target → required annual rate (bisection)."""
    result = simulate_reverse_to_rate(
        current_age=inputs.current_age,
        retire_age=inputs.retire_age,
        life_expectancy=inputs.life_expectancy,
        current_assets_twd=inputs.current_assets_twd,
        monthly_saving_twd=inputs.monthly_saving_twd,
        target_monthly_expense_twd=inputs.target_monthly_expense_twd,
        inflation_rate=inflation_rate if inflation_rate is not None else C.DEFAULT_INFLATION_RATE,
    )
    return {
        "inputs": asdict(inputs),
        "result": asdict(result),
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


def run_compare(
    inputs: SimulatorInputs,
    *,
    modules: set[str] | None = None,
    inflation_rate: float | None = None,
) -> dict[str, Any]:
    """A/B/C 個別模組總覽 — one card per selected module. category_level only."""
    module_set = {m.strip().upper() for m in (modules or set(inputs.selected_modules))}
    invalid = module_set - VALID_MODULES
    if invalid or not module_set:
        module_set = {"A"}
    projections = compare_allocations(
        current_age=inputs.current_age,
        retire_age=inputs.retire_age,
        life_expectancy=inputs.life_expectancy,
        current_assets_twd=inputs.current_assets_twd,
        monthly_saving_twd=inputs.monthly_saving_twd,
        target_monthly_expense_twd=inputs.target_monthly_expense_twd,
        inflation_rate=inflation_rate if inflation_rate is not None else C.DEFAULT_INFLATION_RATE,
        selected_modules=module_set,
    )
    ltc_reserve = None
    if "C" in module_set:
        ltc_reserve = {
            "applies_to_modules": ["C"],
            "suggested_reserve_pct_range": [0.05, 0.10],
            "monthly_reserve_range_twd": [
                round(inputs.monthly_saving_twd * 0.05, 2),
                round(inputs.monthly_saving_twd * 0.10, 2),
            ],
            "estimation_type": "category_level",
            "note": (
                "長照模組建議自月投入中預留 5-10% 作為失能 / 長照保障預算。"
                "此為類別粗估，實際保額與年繳保費請以保險公司正式建議書為準。"
            ),
        }
    return {
        "inputs": asdict(inputs),
        "selected_modules": sorted(module_set),
        "estimation_type": "category_level",
        "category_rates": {
            "investment": C.ETF_CATEGORY_RATE,
            "insurance": C.INSURANCE_CATEGORY_RATE,
            "cash": C.CASH_CATEGORY_RATE,
        },
        "inflation_rate": C.DEFAULT_INFLATION_RATE,
        "allocations": [asdict(p) for p in projections],
        "ltc_reserve": ltc_reserve,
        "assumptions": ASSUMPTIONS,
        "disclaimer": strategy_disclaimer(),
    }
