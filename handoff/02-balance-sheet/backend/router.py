from typing import Any

from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.db import get_connection
from app.services.balance_sheet_utils import compute_summary

router = APIRouter()


def sync_financials(cur: Any, client_id: int, assets: dict[str, Any], liabilities: dict[str, Any]) -> None:
    summary = compute_summary(assets, liabilities)
    cur.execute(
        """
          INSERT INTO client_financials (
            client_id, monthly_income, monthly_expense, current_assets, current_liabilities, monthly_investable
          )
          VALUES (%s, %s, %s, %s, %s, %s)
          ON CONFLICT (client_id) DO UPDATE SET
            monthly_income = EXCLUDED.monthly_income,
            monthly_expense = EXCLUDED.monthly_expense,
            current_assets = EXCLUDED.current_assets,
            current_liabilities = EXCLUDED.current_liabilities,
            monthly_investable = EXCLUDED.monthly_investable,
            updated_at = CURRENT_TIMESTAMP
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


@router.get("/{client_id}/balance-sheet")
def get_balance_sheet(client_id: int) -> dict[str, Any] | None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM client_balance_sheet WHERE client_id = %s", (client_id,))
            row = cur.fetchone()
            return row if row else None
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch balance sheet") from exc


@router.post("/{client_id}/balance-sheet")
def upsert_balance_sheet(client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    assets = payload.get("assets") or {}
    liabilities = payload.get("liabilities") or {}
    summary = compute_summary(assets, liabilities)

    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                          INSERT INTO client_balance_sheet (
                            client_id, assets, liabilities, total_assets, total_liabilities, net_worth,
                            monthly_income, monthly_expense, monthly_balance
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                          ON CONFLICT (client_id) DO UPDATE SET
                            assets = EXCLUDED.assets,
                            liabilities = EXCLUDED.liabilities,
                            total_assets = EXCLUDED.total_assets,
                            total_liabilities = EXCLUDED.total_liabilities,
                            net_worth = EXCLUDED.net_worth,
                            monthly_income = EXCLUDED.monthly_income,
                            monthly_expense = EXCLUDED.monthly_expense,
                            monthly_balance = EXCLUDED.monthly_balance,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            client_id,
                            Json(assets),
                            Json(liabilities),
                            summary["totalAssets"],
                            summary["totalLiabilities"],
                            summary["netWorth"],
                            summary["monthlyIncome"],
                            summary["monthlyExpense"],
                            summary["monthlyBalance"],
                        ),
                    )
                    sync_financials(cur, client_id, assets, liabilities)
        return {"message": "Balance sheet saved", "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save balance sheet") from exc


