"""Retirement simulator — product-agnostic compounding engine.

Locked assumptions (see docs / Batch 1 plan):
- Annual compounding (not monthly).
- Post-retirement portfolio keeps earning at
  ``rate * POST_RETIREMENT_RATE_FACTOR`` (default 50% of accumulation rate).
- Asset trajectory targets zero at ``life_expectancy`` (no residual estate).
- ``reverse_to_rate`` uses bisection on [0%, 15%] because the target
  function is monotonic in r.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    DEFAULT_ANNUAL_RATE,
    DEFAULT_INFLATION_RATE,
    POST_RETIREMENT_RATE_FACTOR,
    REVERSE_RATE_MAX_ITER,
    REVERSE_RATE_SEARCH_BOUNDS,
    REVERSE_RATE_TOLERANCE,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _fv_annuity(rate: float, periods: int) -> float:
    if periods <= 0:
        return 0.0
    if rate == 0:
        return float(periods)
    return ((1 + rate) ** periods - 1) / rate


def _pv_annuity(rate: float, periods: int) -> float:
    if periods <= 0:
        return 0.0
    if rate == 0:
        return float(periods)
    return (1 - (1 + rate) ** -periods) / rate


def _validate_ages(current_age: int, retire_age: int, life_expectancy: int) -> None:
    if current_age < 0 or retire_age <= current_age or life_expectancy <= retire_age:
        raise ValueError(
            "Ages must satisfy 0 <= current_age < retire_age < life_expectancy"
        )


# ── Output dataclasses ────────────────────────────────────────────────────

@dataclass
class YearlyAssetPoint:
    age: int
    year_offset: int
    assets_twd: float


@dataclass
class ForwardResult:
    """Output of ``simulate_forward``."""

    years_to_retire: int
    years_in_retirement: int
    annual_rate: float
    inflation_rate: float

    future_value_at_retire_twd: float
    required_total_at_retire_twd: float
    affordable_monthly_withdrawal_twd: float
    achievement_ratio: float
    yearly_assets: list[YearlyAssetPoint] = field(default_factory=list)


@dataclass
class ReverseToSavingResult:
    """Output of ``simulate_reverse_to_saving``."""

    years_to_retire: int
    years_in_retirement: int
    annual_rate: float
    inflation_rate: float
    required_monthly_saving_twd: float
    required_total_at_retire_twd: float


@dataclass
class ReverseToRateResult:
    """Output of ``simulate_reverse_to_rate``."""

    years_to_retire: int
    years_in_retirement: int
    required_annual_rate: float | None
    required_total_at_retire_twd: float
    converged: bool
    iterations: int


# ── Mode 1: forward ───────────────────────────────────────────────────────

def simulate_forward(
    *,
    current_age: int,
    retire_age: int,
    life_expectancy: int,
    current_assets_twd: float,
    monthly_saving_twd: float,
    target_monthly_expense_twd: float,
    annual_rate: float = DEFAULT_ANNUAL_RATE,
    inflation_rate: float = DEFAULT_INFLATION_RATE,
) -> ForwardResult:
    """Given savings plan → project assets, withdrawable income, achievement.

    The yearly asset path includes one point per age from ``current_age`` to
    ``life_expectancy`` inclusive.
    """

    _validate_ages(current_age, retire_age, life_expectancy)
    n = retire_age - current_age
    retire_years = life_expectancy - retire_age

    # Accumulation phase: existing principal compounds, contributions grow FV annuity.
    fv_at_retire = (
        current_assets_twd * (1 + annual_rate) ** n
        + monthly_saving_twd * 12 * _fv_annuity(annual_rate, n)
    )

    # Required total at retirement to sustain target withdrawals through retire_years.
    inflated_monthly = target_monthly_expense_twd * (1 + inflation_rate) ** n
    real_rate = (1 + annual_rate) / (1 + inflation_rate) - 1
    required_total = inflated_monthly * 12 * _pv_annuity(
        real_rate if real_rate > 0 else 0.001, retire_years
    )

    # Affordable monthly withdrawal implied by the projected FV.
    post_retire_rate = annual_rate * POST_RETIREMENT_RATE_FACTOR
    affordable_monthly = 0.0
    if retire_years > 0:
        pv_factor = _pv_annuity(post_retire_rate, retire_years)
        if pv_factor > 0:
            affordable_monthly = fv_at_retire / (pv_factor * 12)

    achievement = (
        affordable_monthly / inflated_monthly if inflated_monthly > 0 else 0.0
    )

    # Build yearly asset path.
    yearly: list[YearlyAssetPoint] = []
    assets = float(current_assets_twd)
    for i in range(n + 1):
        yearly.append(
            YearlyAssetPoint(
                age=current_age + i,
                year_offset=i,
                assets_twd=round(assets, 2),
            )
        )
        if i < n:
            assets = assets * (1 + annual_rate) + monthly_saving_twd * 12

    annual_expense = inflated_monthly * 12
    for j in range(1, retire_years + 1):
        assets = assets * (1 + post_retire_rate) - annual_expense
        if assets < 0:
            assets = 0.0
        yearly.append(
            YearlyAssetPoint(
                age=retire_age + j,
                year_offset=n + j,
                assets_twd=round(assets, 2),
            )
        )
        annual_expense *= 1 + inflation_rate

    return ForwardResult(
        years_to_retire=n,
        years_in_retirement=retire_years,
        annual_rate=annual_rate,
        inflation_rate=inflation_rate,
        future_value_at_retire_twd=round(fv_at_retire, 2),
        required_total_at_retire_twd=round(required_total, 2),
        affordable_monthly_withdrawal_twd=round(affordable_monthly, 2),
        achievement_ratio=round(achievement, 4),
        yearly_assets=yearly,
    )


# ── Mode 2: reverse → required monthly saving ─────────────────────────────

def simulate_reverse_to_saving(
    *,
    current_age: int,
    retire_age: int,
    life_expectancy: int,
    current_assets_twd: float,
    target_monthly_expense_twd: float = 0.0,
    target_corpus_twd: float = 0.0,
    target_kind: str = "monthly",
    annual_rate: float = DEFAULT_ANNUAL_RATE,
    inflation_rate: float = DEFAULT_INFLATION_RATE,
) -> ReverseToSavingResult:
    """Given target → required monthly saving.

    ``target_kind='monthly'`` (default): target = 退休後每月想領（今日幣值），
    系統自動套通膨 + 年金現值法回推退休總資金。

    ``target_kind='corpus'``: target = 退休時想累積到的總資金（未來幣值），
    跳過月領 → 總資金的年金現值轉換步驟。對應保經第 3 個情境
    「我退休時想要有 X 萬，每月該存多少」。
    """

    _validate_ages(current_age, retire_age, life_expectancy)
    n = retire_age - current_age
    retire_years = life_expectancy - retire_age

    if target_kind == "corpus":
        required_total = float(target_corpus_twd)
    else:
        inflated_monthly = target_monthly_expense_twd * (1 + inflation_rate) ** n
        post_retire_rate = annual_rate * POST_RETIREMENT_RATE_FACTOR
        required_total = inflated_monthly * 12 * _pv_annuity(post_retire_rate, retire_years)

    remaining = required_total - current_assets_twd * (1 + annual_rate) ** n
    if remaining <= 0 or n <= 0:
        required_monthly = 0.0
    else:
        fv_factor = _fv_annuity(annual_rate, n)
        required_monthly = remaining / (fv_factor * 12) if fv_factor > 0 else 0.0

    return ReverseToSavingResult(
        years_to_retire=n,
        years_in_retirement=retire_years,
        annual_rate=annual_rate,
        inflation_rate=inflation_rate,
        required_monthly_saving_twd=round(max(required_monthly, 0.0), 2),
        required_total_at_retire_twd=round(required_total, 2),
    )


# ── Mode 3: reverse-reverse → required annual rate (bisection) ────────────

def _fv_given_rate(
    *,
    current_assets_twd: float,
    monthly_saving_twd: float,
    years_to_retire: int,
    rate: float,
) -> float:
    return (
        current_assets_twd * (1 + rate) ** years_to_retire
        + monthly_saving_twd * 12 * _fv_annuity(rate, years_to_retire)
    )


def simulate_reverse_to_rate(
    *,
    current_age: int,
    retire_age: int,
    life_expectancy: int,
    current_assets_twd: float,
    monthly_saving_twd: float,
    target_monthly_expense_twd: float,
    inflation_rate: float = DEFAULT_INFLATION_RATE,
) -> ReverseToRateResult:
    """Given savings plan and withdrawal target → required annual rate.

    Uses bisection on [0%, 15%]. The function
    ``fv_given_rate(r) - required_total(r)`` is monotonically increasing in
    r over the search range for realistic inputs, so bisection converges.
    """

    _validate_ages(current_age, retire_age, life_expectancy)
    n = retire_age - current_age
    retire_years = life_expectancy - retire_age

    def shortfall(rate: float) -> float:
        fv = _fv_given_rate(
            current_assets_twd=current_assets_twd,
            monthly_saving_twd=monthly_saving_twd,
            years_to_retire=n,
            rate=rate,
        )
        post = rate * POST_RETIREMENT_RATE_FACTOR
        inflated_monthly = target_monthly_expense_twd * (1 + inflation_rate) ** n
        required = inflated_monthly * 12 * _pv_annuity(post if post > 0 else 0.001, retire_years)
        return fv - required

    low, high = REVERSE_RATE_SEARCH_BOUNDS
    f_low = shortfall(low)
    f_high = shortfall(high)

    if f_low >= 0:
        # Already meets target even at 0% — no investment return needed.
        post = low * POST_RETIREMENT_RATE_FACTOR
        required_total = (
            target_monthly_expense_twd * (1 + inflation_rate) ** n
            * 12 * _pv_annuity(post if post > 0 else 0.001, retire_years)
        )
        return ReverseToRateResult(
            years_to_retire=n,
            years_in_retirement=retire_years,
            required_annual_rate=low,
            required_total_at_retire_twd=round(required_total, 2),
            converged=True,
            iterations=0,
        )

    if f_high < 0:
        # Even at the max search rate, plan falls short — unreachable.
        return ReverseToRateResult(
            years_to_retire=n,
            years_in_retirement=retire_years,
            required_annual_rate=None,
            required_total_at_retire_twd=0.0,
            converged=False,
            iterations=0,
        )

    iterations = 0
    mid = (low + high) / 2
    for iterations in range(1, REVERSE_RATE_MAX_ITER + 1):
        mid = (low + high) / 2
        fm = shortfall(mid)
        if abs(fm) < 1.0 or (high - low) < REVERSE_RATE_TOLERANCE:
            break
        if fm < 0:
            low = mid
        else:
            high = mid

    post = mid * POST_RETIREMENT_RATE_FACTOR
    required_total = (
        target_monthly_expense_twd * (1 + inflation_rate) ** n
        * 12 * _pv_annuity(post if post > 0 else 0.001, retire_years)
    )

    return ReverseToRateResult(
        years_to_retire=n,
        years_in_retirement=retire_years,
        required_annual_rate=round(mid, 6),
        required_total_at_retire_twd=round(required_total, 2),
        converged=(high - low) < REVERSE_RATE_TOLERANCE * 10,
        iterations=iterations,
    )
