import json
from typing import Any

from fastapi import APIRouter, HTTPException

from db import get_connection, row_to_dict
from services.balance_sheet_utils import compute_summary

router = APIRouter()


@router.get("/{client_id}/balance-sheet")
def get_balance_sheet(client_id: int) -> dict[str, Any] | None:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM client_balance_sheet WHERE client_id = ?", (client_id,))
            row = cur.fetchone()
            return row_to_dict(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch balance sheet") from exc


@router.post("/{client_id}/balance-sheet")
def upsert_balance_sheet(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    assets = payload.get("assets") or {}
    liabilities = payload.get("liabilities") or {}
    summary = compute_summary(assets, liabilities)

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO client_balance_sheet (
                    client_id, assets, liabilities, total_assets, total_liabilities, net_worth,
                    monthly_income, monthly_expense, monthly_balance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    assets=excluded.assets,
                    liabilities=excluded.liabilities,
                    total_assets=excluded.total_assets,
                    total_liabilities=excluded.total_liabilities,
                    net_worth=excluded.net_worth,
                    monthly_income=excluded.monthly_income,
                    monthly_expense=excluded.monthly_expense,
                    monthly_balance=excluded.monthly_balance,
                    updated_at=datetime('now')
                """,
                (
                    client_id,
                    json.dumps(assets),
                    json.dumps(liabilities),
                    summary["totalAssets"],
                    summary["totalLiabilities"],
                    summary["netWorth"],
                    summary["monthlyIncome"],
                    summary["monthlyExpense"],
                    summary["monthlyBalance"],
                ),
            )
            # sync client_financials
            cur.execute(
                """
                INSERT INTO client_financials (
                    client_id, monthly_income, monthly_expense, current_assets, current_liabilities,
                    monthly_investable
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    monthly_income=excluded.monthly_income,
                    monthly_expense=excluded.monthly_expense,
                    current_assets=excluded.current_assets,
                    current_liabilities=excluded.current_liabilities,
                    monthly_investable=excluded.monthly_investable,
                    updated_at=datetime('now')
                """,
                (
                    client_id,
                    summary["monthlyIncome"],
                    summary["monthlyExpense"],
                    summary["totalAssets"],
                    summary["totalLiabilities"],
                    summary["monthlyBalance"],
                ),
            )
        return {"message": "Balance sheet saved", "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save balance sheet") from exc
