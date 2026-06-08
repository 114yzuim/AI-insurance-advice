"""Neutral defaults for the retirement simulator.

Design notes:
- No risk-persona labels ("保守/基準/積極") on customer-facing surfaces.
- A single neutral default rate is exposed to the UI slider.
- Internal category rates (ETF / insurance) are retained for the individual
  module overview but never labelled with risk-persona terms.
"""

from __future__ import annotations

# ── Customer-facing defaults ──────────────────────────────────────────────

DEFAULT_ANNUAL_RATE: float = 0.06
DEFAULT_INFLATION_RATE: float = 0.025

# Inclusive slider bounds shown to the customer.
# Upper bound 0.20 gives headroom beyond the 0.15 reverse-rate search ceiling,
# so forward-mode users can explore high-return assumptions without
# hitting a visual cap.
RATE_BOUNDS: tuple[float, float] = (0.02, 0.20)

# Post-retirement portfolio growth factor, applied inside core.simulate_forward.
#
# 2026-04-23 decision: set to 0.0 (retirement assets do NOT grow). Previously
# was 0.5, which caused a hidden assumption — users setting "10% annual" saw
# retirement assets actually grow at 5%, lengthening decay from ~13 years to
# ~22 years in ways that didn't match intuition.
#
# With factor = 0:
#   - accumulation period uses the user's annual_rate slider
#   - retirement period = pure drawdown (no asset growth, only inflation on
#     expenses)
# Brokers who want to model "some retirement growth" can simply reduce the
# accumulation rate to an average that includes the retirement drift.
POST_RETIREMENT_RATE_FACTOR: float = 0.0

# ── reverse_to_rate solver ────────────────────────────────────────────────

REVERSE_RATE_SEARCH_BOUNDS: tuple[float, float] = (0.0, 0.15)
REVERSE_RATE_TOLERANCE: float = 1e-5
REVERSE_RATE_MAX_ITER: int = 50

# ── Individual module overview ───────────────────────────────────────────
# Category-level assumed rates — NOT real product yields. Used only to show
# each A/B/C module by itself. Integrated allocation mixes are intentionally
# excluded from the current round; they belong to the next "配比建議" phase.

ETF_CATEGORY_RATE: float = 0.06
INSURANCE_CATEGORY_RATE: float = 0.022
CASH_CATEGORY_RATE: float = 0.01

MODULE_RATE_BASIS: dict[str, str] = {
    "A": (
        "依據：MSCI ACWI 1990-2025 年化約 6.5%；勞退新制保證約 3%。"
        "此處用 6.0% 作為投資類別教學估值，實際因配置與市況而異。"
    ),
    "B": (
        "依據：21 檔利變 / 還本壽險 guaranteed_rate 約 2.0%、"
        "non-guaranteed_rate 約 2.4%。此處用 2.2% 作為保險類別 IRR 教學估值，"
        "實際依商品條款、宣告利率與年度而異。"
    ),
    "C": (
        "C 模組不看報酬率；以每月可存金額的 5-10% 估失能 / 長照保費準備，"
        "並用保費約 10 倍粗估月給付。此為教學估值，實際依長照機構與商品條款而異。"
    ),
}


def module_category_rates() -> dict[str, float]:
    """Return current module rates from constants, avoiding stale copies."""
    return {
        "A": ETF_CATEGORY_RATE,
        "B": INSURANCE_CATEGORY_RATE,
        "C": 0.0,
    }


def format_rate_percent(rate: float) -> str:
    """Render a rate constant for human-facing disclaimer text."""
    rendered = f"{rate * 100:.1f}".rstrip("0").rstrip(".")
    return f"{rendered}%"


def module_rate_basis() -> dict[str, str]:
    """Return basis copy that stays in sync with rate constants."""
    basis = dict(MODULE_RATE_BASIS)
    basis["A"] = (
        "依據：MSCI ACWI 1990-2025 年化約 6.5%；勞退新制保證約 3%。"
        f"此處用 {format_rate_percent(ETF_CATEGORY_RATE)} 作為投資類別教學估值，"
        "實際因配置與市況而異。"
    )
    basis["B"] = (
        "依據：21 檔利變 / 還本壽險 guaranteed_rate 約 2.0%、"
        "non-guaranteed_rate 約 2.4%。"
        f"此處用 {format_rate_percent(INSURANCE_CATEGORY_RATE)} 作為保險類別 IRR 教學估值，"
        "實際依商品條款、宣告利率與年度而異。"
    )
    return basis

# ── IRR 預設值校準依據（2026-04-27） ─────────────────────────────────────
# 數字參考 app/data/insurance_products_legacy21.json 21 檔利變/還本壽險：
#   guaranteed_rate 範圍：1.0% (2年期) / 1.75% (6/10年期) / 2.0% / 2.25% — 中位數約 2.0%
#   non_guaranteed_rate 範圍：2.30% / 2.50% — 中位數約 2.4%
# 真實 IRR 區間：保守看 2.0%，宣告利率高峰約 2.5%。
# 對應 Simulator UI 的 ⓘ icon tooltip（見 module_rate_basis()）


# One row per selected module. Do not add 70/30 or 40/60 here; those are
# integrated allocation recommendations and should stay out until the next
# product phase.
MODULE_PROJECTION_PRESETS: tuple[dict[str, float | str], ...] = (
    {
        "id": "module_a_investment",
        "module": "A",
        "name": "模組 A · 投資",
        "projection_type": "financial_accumulation",
        "annual_rate": ETF_CATEGORY_RATE,
        "investment_pct": 1.0,
        "insurance_pct": 0.0,
        "cash_pct": 0.0,
    },
    {
        "id": "module_b_insurance",
        "module": "B",
        "name": "模組 B · 保險",
        "projection_type": "financial_accumulation",
        "annual_rate": INSURANCE_CATEGORY_RATE,
        "investment_pct": 0.0,
        "insurance_pct": 1.0,
        "cash_pct": 0.0,
    },
    {
        "id": "module_c_ltc",
        "module": "C",
        "name": "模組 C · 失能長照",
        "projection_type": "ltc_hedge",
        "annual_rate": 0.0,
        "investment_pct": 0.0,
        "insurance_pct": 0.0,
        "cash_pct": 0.0,
    },
)

# Long-term care / disability category heuristic: 月繳保費 × N ≈ 失能月給付。
# Typical rider structures fall in the 5–15× band; 10× is the midpoint
# we expose to the UI. This is a TEACHING ratio, not a product quote.
LTC_BENEFIT_TO_PREMIUM_RATIO: float = 10.0
# Range shown to brokers as the self-pay alternative if no LTC coverage.
# Source basis (2026-04-27):
# - MOHW accommodation-institution subsidy: up to 120k/year, implying
#   government treats institutional care as a recurring high-cost burden.
# - SmartBeb insurance education estimates local LTC institutions or
#   Taiwan-native caregivers can reach 50k-100k+/month.
# - Business Weekly / Commonwealth retirement-insurance coverage commonly
#   cites institutional or long-term care costs around 50k-60k+/month.
# We use 50k-80k as a conservative teaching range, not a product quote.
LTC_SELF_PAY_MONTHLY_RANGE_TWD: tuple[int, int] = (50_000, 80_000)
