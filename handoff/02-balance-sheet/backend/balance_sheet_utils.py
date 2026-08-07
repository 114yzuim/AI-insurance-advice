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


# 不具流動性的投資欄位，不計入流動資產
_ILLIQUID_INVESTMENT_KEYS = {"lent_to_others"}


def compute_liquid_assets(raw_assets: Any) -> float:
    """Return sum of cash + investment from balance-sheet assets JSONB.

    Excludes property/real_estate/movable/other — these are illiquid and
    should NOT be counted toward the retirement gap calculation.
    Also excludes lent_to_others within investment (non-liquid receivable).
    """
    if not raw_assets or not isinstance(raw_assets, dict):
        return 0.0
    return (
        _sum_num(raw_assets.get("cash"))
        + _sum_num(raw_assets.get("investment"), exclude_keys=_ILLIQUID_INVESTMENT_KEYS)
    )


def compute_summary(assets: dict[str, Any], liabilities: dict[str, Any]) -> dict[str, float]:
    total_assets = (
        _sum_num(assets.get("cash"))
        + _sum_num(assets.get("investment"))
        + _sum_num(assets.get("movable"))
        + _sum_num(assets.get("real_estate"))
        + _sum_num(assets.get("revolving"))
    )

    fixed = liabilities.get("fixed") or {}
    fixed_slots = list(fixed.values())

    total_debt_balance = 0.0
    total_fixed_monthly = 0.0
    for debt in fixed_slots:
        if isinstance(debt, dict):
            total_debt_balance += float(debt.get("balance") or 0)
            total_fixed_monthly += float(debt.get("monthly_payment") or 0)

    total_general_monthly = _sum_num(liabilities.get("general"))

    monthly_income = _sum_num(assets.get("income"))
    monthly_expense = total_fixed_monthly + total_general_monthly
    monthly_balance = monthly_income - monthly_expense
    net_worth = total_assets - total_debt_balance
    total_liabilities = total_debt_balance

    return {
        "totalAssets": total_assets,
        "totalLiabilities": total_liabilities,
        "netWorth": net_worth,
        "monthlyIncome": monthly_income,
        "monthlyExpense": monthly_expense,
        "monthlyBalance": monthly_balance,
    }


def compute_summary_from_raw_jsonb(raw_assets: Any, raw_liabilities: Any) -> dict[str, float]:
    assets = raw_assets or {
        "cash": {},
        "investment": {},
        "movable": {},
        "real_estate": {},
        "revolving": {},
        "income": {},
    }
    liabilities = raw_liabilities or {"fixed": {}, "general": {}}
    return compute_summary(assets, liabilities)


ALLOC_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#ec4899"]


def compute_asset_allocation(raw_assets: Any) -> list[dict[str, Any]]:
    if not raw_assets:
        return []

    categories = [
        {"label": "現金/存款", "value": _sum_num(raw_assets.get("cash"))},
        {"label": "投資/保險", "value": _sum_num(raw_assets.get("investment"))},
        {
            "label": "不動產/動產",
            "value": _sum_num(raw_assets.get("property"))
            + _sum_num(raw_assets.get("movable"))
            + _sum_num(raw_assets.get("real_estate")),
        },
        {
            "label": "其他資產",
            "value": _sum_num(raw_assets.get("other")) + _sum_num(raw_assets.get("revolving")),
        },
    ]

    total = sum(c["value"] for c in categories)
    if total == 0:
        return []

    output: list[dict[str, Any]] = []
    color_index = 0
    for category in categories:
        if category["value"] <= 0:
            continue
        output.append(
            {
                "name": category["label"],
                "label": category["label"],
                "value": category["value"],
                "percentage": round(category["value"] / total * 1000) / 10,
                "color": ALLOC_COLORS[color_index % len(ALLOC_COLORS)],
            }
        )
        color_index += 1
    return output


def compute_post_plan_allocation(
    raw_assets: Any,
    planned_invest_twd: float,
    total_dividends_twd: float,
) -> list[dict[str, Any]]:
    if not raw_assets:
        return []

    categories = [
        {"label": "現金/存款", "value": _sum_num(raw_assets.get("cash"))},
        {
            "label": "投資/保險",
            "value": _sum_num(raw_assets.get("investment")) + planned_invest_twd + total_dividends_twd,
        },
        {
            "label": "不動產/動產",
            "value": _sum_num(raw_assets.get("property"))
            + _sum_num(raw_assets.get("movable"))
            + _sum_num(raw_assets.get("real_estate")),
        },
        {
            "label": "其他資產",
            "value": _sum_num(raw_assets.get("other")) + _sum_num(raw_assets.get("revolving")),
        },
    ]

    total = sum(c["value"] for c in categories)
    if total == 0:
        return []

    output: list[dict[str, Any]] = []
    color_index = 0
    for category in categories:
        if category["value"] <= 0:
            continue
        output.append(
            {
                "name": category["label"],
                "label": category["label"],
                "value": category["value"],
                "percentage": round(category["value"] / total * 1000) / 10,
                "color": ALLOC_COLORS[color_index % len(ALLOC_COLORS)],
            }
        )
        color_index += 1
    return output


