"""Simulator endpoints — product-agnostic retirement projections.

Design principles:
- No product names, product codes, or company identifiers are referenced.
- Numbers are illustrative projections, not insurance-company 建議書.
- Inputs are intentionally narrow (age triples + principal + monthly + target + rate).
"""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

from app.db import get_connection
from app.services.simulator import constants as sim_constants
from app.services.simulator.core import (
    simulate_forward,
    simulate_reverse_to_rate,
    simulate_reverse_to_saving,
)

router = APIRouter()

DISCLAIMER = (
    "本試算為概念性數字，非保險公司正式建議書。"
    "所有報酬率為假設值，實際結果會受市場、通膨、健康變化影響。"
)

# Transparent assumptions — returned on every response so the UI can render
# the 「計算前提」 section and users can judge the model.
ASSUMPTIONS: dict[str, Any] = {
    "compounding": "annual",
    "compounding_description": "資產與每月投入採年複利計算（非月複利）。",
    "post_retirement_still_investing": sim_constants.POST_RETIREMENT_RATE_FACTOR > 0,
    "post_retirement_rate_factor": sim_constants.POST_RETIREMENT_RATE_FACTOR,
    "post_retirement_rate_description": (
        "退休後資產純提領、不再成長（pure drawdown）。若需模擬「退休後仍有部分成長」，"
        "請降低累積期年化報酬率滑桿以反映平均值。"
        if sim_constants.POST_RETIREMENT_RATE_FACTOR == 0
        else f"退休後資產仍持續投資，但報酬率降為累積期的 "
        f"{int(sim_constants.POST_RETIREMENT_RATE_FACTOR * 100)}%。"
    ),
    "withdrawal_model": "annuity_pv",
    "withdrawal_model_description": (
        "月領金額以年金現值法推算，假設資產於預期壽命當年耗盡至零（無身後留存）。"
    ),
    "inflation_included": True,
    "inflation_description": (
        "通膨率套用於退休當期的目標月支出：目標月支出 × (1 + 通膨)^(退休年 − 當前年齡)。"
    ),
    "reverse_rate_method": "bisection",
    "reverse_rate_method_description": (
        "反推所需報酬率採用二分法搜尋 [0%, 15%]，收斂容忍度 1e-5，最多 50 次迭代。"
    ),
}


def _coalesce(value: Any, default: Any) -> Any:
    return default if value is None else value


def _pick(payload: dict[str, Any], *keys: str) -> Any:
    """Return the first non-None value from payload matching any of the given keys.

    Accepts both legacy names (``current_assets``) and the ``_twd`` suffixed
    names the frontend actually sends (``current_assets_twd``). Without this,
    updates to numeric inputs in the UI silently fall back to DB defaults.
    """
    for k in keys:
        v = payload.get(k)
        if v is not None:
            return v
    return None


def _resolve_ages_and_assets(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge payload overrides with DB defaults for client."""

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
              SELECT c.age, c.target_retire_age, c.life_expectancy,
                     c.is_joint_plan, c.spouse_age, c.spouse_life_expectancy,
                     c.selected_modules,
                     f.current_assets, f.monthly_investable,
                     f.target_retire_monthly_expense
              FROM clients c
              LEFT JOIN client_financials f ON f.client_id = c.id
              WHERE c.id = %s
            """,
            (client_id,),
        )
        client = cur.fetchone()

    if not client:
        raise HTTPException(status_code=404, detail="找不到客戶")

    is_joint = bool(client.get("is_joint_plan")) and bool(client.get("spouse_age"))
    default_life = (
        max(
            int(client.get("life_expectancy") or 85),
            int(client.get("spouse_life_expectancy") or 85),
        )
        if is_joint
        else int(client.get("life_expectancy") or 85)
    )
    expense_multiplier = 1.6 if is_joint else 1.0

    current_assets_override = _pick(payload, "current_assets_twd", "current_assets")
    monthly_saving_override = _pick(payload, "monthly_saving_twd", "monthly_saving")
    target_expense_override = _pick(
        payload, "target_monthly_expense_twd", "target_monthly_expense"
    )

    return {
        "current_age": int(_coalesce(payload.get("current_age"), client.get("age")) or 35),
        "retire_age": int(_coalesce(payload.get("retire_age"), client.get("target_retire_age")) or 65),
        "life_expectancy": int(_coalesce(payload.get("life_expectancy"), default_life) or 85),
        "current_assets_twd": float(
            current_assets_override
            if current_assets_override is not None
            else (client.get("current_assets") or 0)
        ),
        "monthly_saving_twd": float(
            monthly_saving_override
            if monthly_saving_override is not None
            else (client.get("monthly_investable") or 0)
        ),
        "target_monthly_expense_twd": float(
            target_expense_override
            if target_expense_override is not None
            else (float(client.get("target_retire_monthly_expense") or 40000) * expense_multiplier)
        ),
        "selected_modules": list(client.get("selected_modules") or ["A"]),
    }


@router.get("/{client_id}/defaults")
def get_defaults(client_id: int) -> dict[str, Any]:
    """Return pre-filled defaults so the simulator page can render on first load."""

    inputs = _resolve_ages_and_assets(client_id, payload={})
    return {
        **inputs,
        "annual_rate": sim_constants.DEFAULT_ANNUAL_RATE,
        "inflation_rate": sim_constants.DEFAULT_INFLATION_RATE,
        "rate_bounds": {
            "min": sim_constants.RATE_BOUNDS[0],
            "max": sim_constants.RATE_BOUNDS[1],
        },
        "category_rates": sim_constants.module_category_rates(),
        "module_rate_basis": sim_constants.module_rate_basis(),
        "ltc_benefit_ratio": sim_constants.LTC_BENEFIT_TO_PREMIUM_RATIO,
        "ltc_self_pay_monthly_range": list(sim_constants.LTC_SELF_PAY_MONTHLY_RANGE_TWD),
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


@router.post("/{client_id}/forward")
def forward(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 1: savings plan → future value, withdrawable income, achievement."""

    inputs = _resolve_ages_and_assets(client_id, payload)
    try:
        result = simulate_forward(
            current_age=inputs["current_age"],
            retire_age=inputs["retire_age"],
            life_expectancy=inputs["life_expectancy"],
            current_assets_twd=inputs["current_assets_twd"],
            monthly_saving_twd=inputs["monthly_saving_twd"],
            target_monthly_expense_twd=inputs["target_monthly_expense_twd"],
            annual_rate=float(_coalesce(payload.get("annual_rate"), sim_constants.DEFAULT_ANNUAL_RATE)),
            inflation_rate=float(_coalesce(payload.get("inflation_rate"), sim_constants.DEFAULT_INFLATION_RATE)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "inputs": inputs,
        "result": asdict(result),
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


@router.post("/{client_id}/reverse-saving")
def reverse_saving(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 2: target → required monthly saving.

    target_kind:
      'monthly' (default) — payload.target_monthly_expense_twd
      'corpus'             — payload.target_corpus_twd 退休時想累積的總資金
    """

    inputs = _resolve_ages_and_assets(client_id, payload)
    target_kind = str(payload.get("target_kind") or "monthly")
    target_corpus = float(_coalesce(payload.get("target_corpus_twd"), 0))
    if target_kind not in ("monthly", "corpus"):
        raise HTTPException(
            status_code=400,
            detail="target_kind must be 'monthly' or 'corpus'",
        )
    if target_kind == "corpus" and target_corpus <= 0:
        raise HTTPException(
            status_code=400,
            detail="target_corpus_twd must be > 0 when target_kind = 'corpus'",
        )
    try:
        result = simulate_reverse_to_saving(
            current_age=inputs["current_age"],
            retire_age=inputs["retire_age"],
            life_expectancy=inputs["life_expectancy"],
            current_assets_twd=inputs["current_assets_twd"],
            target_monthly_expense_twd=inputs["target_monthly_expense_twd"],
            target_corpus_twd=target_corpus,
            target_kind=target_kind,
            annual_rate=float(_coalesce(payload.get("annual_rate"), sim_constants.DEFAULT_ANNUAL_RATE)),
            inflation_rate=float(_coalesce(payload.get("inflation_rate"), sim_constants.DEFAULT_INFLATION_RATE)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "inputs": inputs,
        "result": asdict(result),
        "target_kind": target_kind,
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }


@router.post("/{client_id}/reverse-rate")
def reverse_rate(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 3: savings plan + withdrawal target → required annual rate."""

    inputs = _resolve_ages_and_assets(client_id, payload)
    try:
        result = simulate_reverse_to_rate(
            current_age=inputs["current_age"],
            retire_age=inputs["retire_age"],
            life_expectancy=inputs["life_expectancy"],
            current_assets_twd=inputs["current_assets_twd"],
            monthly_saving_twd=inputs["monthly_saving_twd"],
            target_monthly_expense_twd=inputs["target_monthly_expense_twd"],
            inflation_rate=float(_coalesce(payload.get("inflation_rate"), sim_constants.DEFAULT_INFLATION_RATE)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "inputs": inputs,
        "result": asdict(result),
        "assumptions": ASSUMPTIONS,
        "disclaimer": DISCLAIMER,
    }
