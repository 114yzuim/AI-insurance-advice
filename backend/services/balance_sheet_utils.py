from typing import Any


def _sum_num(data: dict[str, Any] | None, exclude_keys: set[str] | None = None) -> float:
    if not data:
        return 0.0
    total = 0.0
    for key, value in data.items():
        if exclude_keys and key in exclude_keys:
            continue
        if isinstance(value, (int, float)):
            total += float(value)
    return total


def compute_summary(assets: dict[str, Any], liabilities: dict[str, Any]) -> dict[str, float]:
    total_assets = (
        _sum_num(assets.get("cash"))
        + _sum_num(assets.get("investment"))
        + _sum_num(assets.get("movable"))
        + _sum_num(assets.get("real_estate"))
        + _sum_num(assets.get("revolving"))
    )

    fixed = liabilities.get("fixed") or {}
    total_debt_balance = 0.0
    total_fixed_monthly = 0.0
    for debt in fixed.values():
        if isinstance(debt, dict):
            total_debt_balance += float(debt.get("balance") or 0)
            total_fixed_monthly += float(debt.get("monthly_payment") or 0)

    total_general_monthly = _sum_num(liabilities.get("general"))
    monthly_income = _sum_num(assets.get("income"))
    monthly_expense = total_fixed_monthly + total_general_monthly
    monthly_balance = monthly_income - monthly_expense
    net_worth = total_assets - total_debt_balance

    return {
        "totalAssets": total_assets,
        "totalLiabilities": total_debt_balance,
        "netWorth": net_worth,
        "monthlyIncome": monthly_income,
        "monthlyExpense": monthly_expense,
        "monthlyBalance": monthly_balance,
    }
