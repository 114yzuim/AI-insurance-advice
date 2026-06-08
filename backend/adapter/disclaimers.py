"""Compliance text — lifted out of the FastAPI routers.

Original home:
- ``DISCLAIMER`` + ``ASSUMPTIONS``  → app/api/routers/simulator.py
- ``strategy_disclaimer()``         → app/api/routers/strategy.py

These are 法遵紅線 artefacts: every customer-facing 金額 response in the source
system carried ``assumptions`` + ``disclaimer``. Keep returning them from
whatever endpoint you wire the engine into, or you break 紅線 3.

Pure module — no DB, no FastAPI. Imports only from the engine package.
"""

from __future__ import annotations

from typing import Any

from engine import constants as C


DISCLAIMER = (
    "本試算為概念性數字，非保險公司正式建議書。"
    "所有報酬率為假設值，實際結果會受市場、通膨、健康變化影響。"
)

# Transparent assumptions — return on every response so the UI can render the
# 「計算前提」 section and users can judge the model.
ASSUMPTIONS: dict[str, Any] = {
    "compounding": "annual",
    "compounding_description": "資產與每月投入採年複利計算（非月複利）。",
    "post_retirement_still_investing": C.POST_RETIREMENT_RATE_FACTOR > 0,
    "post_retirement_rate_factor": C.POST_RETIREMENT_RATE_FACTOR,
    "post_retirement_rate_description": (
        "退休後資產純提領、不再成長（pure drawdown）。若需模擬「退休後仍有部分成長」，"
        "請降低累積期年化報酬率滑桿以反映平均值。"
        if C.POST_RETIREMENT_RATE_FACTOR == 0
        else f"退休後資產仍持續投資，但報酬率降為累積期的 "
        f"{int(C.POST_RETIREMENT_RATE_FACTOR * 100)}%。"
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


def strategy_disclaimer() -> str:
    """A/B/C 個別模組頁專用 — stays in sync with the category-rate constants."""
    return (
        "本頁僅為「個別模組」試算，不代表任何具體商品或公司。"
        "所有報酬率為類別層假設"
        f"（投資類 {C.format_rate_percent(C.ETF_CATEGORY_RATE)} / "
        f"保險類 {C.format_rate_percent(C.INSURANCE_CATEGORY_RATE)}），"
        "實際結果會因商品條款、市場變化而不同。"
        "A/B/C 整合配比建議屬下一階段功能。"
    )
