"""Strategy layer — individual A/B/C module projections.

**Not** a product-level simulator. Every number returned here is a
category-level estimate (投資類假設 6% / 保險類假設 2.2%).
The API response carries ``estimation_type: "category_level"`` so the UI
can mark the cards clearly and avoid being mistaken for 保險公司建議書.

This module intentionally does not produce integrated 70/30 or 40/60 mixes.
Those are next-phase allocation recommendations, not the current round's
"ABC 各自精緻" work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    CASH_CATEGORY_RATE,
    DEFAULT_INFLATION_RATE,
    ETF_CATEGORY_RATE,
    INSURANCE_CATEGORY_RATE,
    LTC_BENEFIT_TO_PREMIUM_RATIO,
    LTC_SELF_PAY_MONTHLY_RANGE_TWD,
    MODULE_PROJECTION_PRESETS,
)
from .core import simulate_forward


@dataclass
class AllocationProjection:
    id: str
    module: str
    name: str
    projection_type: str
    investment_pct: float
    insurance_pct: float
    cash_pct: float
    assumed_annual_rate: float
    rate_breakdown: dict[str, float]
    future_value_at_retire_twd: float
    required_total_at_retire_twd: float
    affordable_monthly_withdrawal_twd: float
    achievement_ratio: float
    protection_estimates: dict[str, Any]
    ltc_estimates: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


def _rate_breakdown(
    *, investment_pct: float, insurance_pct: float, cash_pct: float
) -> dict[str, float]:
    """Return the visible per-bucket rate contribution."""
    breakdown = {
        "investment": round(investment_pct * ETF_CATEGORY_RATE, 6),
        "insurance": round(insurance_pct * INSURANCE_CATEGORY_RATE, 6),
        "cash": round(cash_pct * CASH_CATEGORY_RATE, 6),
    }
    return breakdown


def _protection_estimate(
    *, monthly_saving_twd: float, insurance_pct: float
) -> dict[str, Any]:
    """Return category-level insurance premium context, not product coverage."""
    annual_insurance_premium = monthly_saving_twd * 12 * insurance_pct
    return {
        "annual_insurance_premium_twd": round(annual_insurance_premium, 2),
        "estimation_type": "category_level",
        "estimation_note": (
            "年繳保費為保險類投入粗估，用於說明 IRR 累積形狀；"
            "不代表壽險保額、醫療給付或任何商品保障。"
        ),
    }


def _ltc_estimate(*, monthly_saving_twd: float) -> dict[str, Any]:
    """Category-level LTC hedge estimate for module C."""
    reserve_low = monthly_saving_twd * 0.05
    reserve_high = monthly_saving_twd * 0.10
    benefit_low = reserve_low * LTC_BENEFIT_TO_PREMIUM_RATIO
    benefit_high = reserve_high * LTC_BENEFIT_TO_PREMIUM_RATIO
    self_pay_low, self_pay_high = LTC_SELF_PAY_MONTHLY_RANGE_TWD
    return {
        "monthly_reserve_range_twd": [round(reserve_low, 2), round(reserve_high, 2)],
        "estimated_monthly_benefit_range_twd": [
            round(benefit_low, 2),
            round(benefit_high, 2),
        ],
        "self_pay_monthly_range_twd": [self_pay_low, self_pay_high],
        "benefit_to_premium_ratio": LTC_BENEFIT_TO_PREMIUM_RATIO,
        "estimation_type": "category_level",
        "estimation_note": (
            "以月投入的 5-10% 作為長照 / 失能保障預算，月給付粗估為月保費 × 10。"
            "5-8 萬自付情境為台灣長照費用教學估值，實際依照護型態、地區、耗材與補助而異。"
            "這是對沖缺口試算，不是退休累積報酬率或商品報價。"
        ),
    }


def _notes_for_module(
    *,
    module: str,
    achievement_ratio: float,
) -> list[str]:
    notes: list[str] = []
    if module == "A":
        notes.append("保經可這樣說：這條的數字最漂亮，但您要能看著 25 年帳戶起伏不慌。")
        notes.append("投資模組：用來看純累積能力，不包含身故 / 醫療 / 長照保障。")
    elif module == "B":
        notes.append("保經可這樣說：換的是「退休那天保證有錢領」，不是贏 IRR。")
        notes.append("保險模組：用來看保險類 IRR 下的累積限制，保障價值需另看保單條款。")
    elif module == "C":
        notes.append("保經可這樣說：沒買的話，失能後每月自付 5-8 萬，5 年就把累積 25 年的退休金吃掉。")
        notes.append("長照模組：重點是失能時的月給付對沖，不應拿 IRR 或累積資產比較。")
        return notes

    if achievement_ratio < 0.8:
        notes.append("目前達成率偏低，建議調整月投入、退休年齡或目標月領。")
    elif achievement_ratio >= 1.2:
        notes.append("目前試算可能已超越目標，可考慮降低月投入或調整目標。")
    return notes


def compare_allocations(
    *,
    current_age: int,
    retire_age: int,
    life_expectancy: int,
    current_assets_twd: float,
    monthly_saving_twd: float,
    target_monthly_expense_twd: float,
    inflation_rate: float = DEFAULT_INFLATION_RATE,
    selected_modules: set[str] | None = None,
) -> list[AllocationProjection]:
    """Run one projection per selected module."""

    results: list[AllocationProjection] = []
    requested = selected_modules or {"A", "B", "C"}
    for alloc in MODULE_PROJECTION_PRESETS:
        module = str(alloc["module"])
        if module not in requested:
            continue

        inv_pct = float(alloc["investment_pct"])
        ins_pct = float(alloc["insurance_pct"])
        cash_pct = float(alloc["cash_pct"])
        projection_type = str(alloc["projection_type"])
        rate = float(alloc["annual_rate"])
        breakdown = _rate_breakdown(
            investment_pct=inv_pct,
            insurance_pct=ins_pct,
            cash_pct=cash_pct,
        )
        ltc_estimates: dict[str, Any] | None = None
        if projection_type == "ltc_hedge":
            projection = simulate_forward(
                current_age=current_age,
                retire_age=retire_age,
                life_expectancy=life_expectancy,
                current_assets_twd=0.0,
                monthly_saving_twd=0.0,
                target_monthly_expense_twd=target_monthly_expense_twd,
                annual_rate=0.0,
                inflation_rate=inflation_rate,
            )
            ltc_estimates = _ltc_estimate(monthly_saving_twd=monthly_saving_twd)
        else:
            projection = simulate_forward(
                current_age=current_age,
                retire_age=retire_age,
                life_expectancy=life_expectancy,
                current_assets_twd=current_assets_twd,
                monthly_saving_twd=monthly_saving_twd,
                target_monthly_expense_twd=target_monthly_expense_twd,
                annual_rate=rate,
                inflation_rate=inflation_rate,
            )

        results.append(
            AllocationProjection(
                id=str(alloc["id"]),
                module=module,
                name=str(alloc["name"]),
                projection_type=projection_type,
                investment_pct=inv_pct,
                insurance_pct=ins_pct,
                cash_pct=cash_pct,
                assumed_annual_rate=rate,
                rate_breakdown=breakdown,
                future_value_at_retire_twd=projection.future_value_at_retire_twd,
                required_total_at_retire_twd=projection.required_total_at_retire_twd,
                affordable_monthly_withdrawal_twd=projection.affordable_monthly_withdrawal_twd,
                achievement_ratio=projection.achievement_ratio,
                protection_estimates=_protection_estimate(
                    monthly_saving_twd=monthly_saving_twd,
                    insurance_pct=ins_pct,
                ),
                ltc_estimates=ltc_estimates,
                notes=_notes_for_module(
                    module=module,
                    achievement_ratio=projection.achievement_ratio,
                ),
            )
        )

    return results
