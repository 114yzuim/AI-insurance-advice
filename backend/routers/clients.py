import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from db import get_connection, row_to_dict
from services.balance_sheet_utils import compute_summary

router = APIRouter()


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    age: int = Field(..., ge=1, le=120)
    gender: str | None = None
    family_status: str | None = None
    children_count: int = Field(default=0, ge=0)
    children_ages: list[int] = Field(default_factory=list)
    occupation: str | None = None
    target_retire_age: int | None = Field(default=65)
    life_expectancy: int | None = Field(default=85)
    risk_tolerance: str | None = None
    planning_goals: list[str] = Field(default_factory=list)
    selected_modules: list[str] = Field(default_factory=lambda: ["A", "B", "C"])
    is_joint_plan: bool = False
    spouse_name: str | None = None
    spouse_age: int | None = None
    spouse_gender: str | None = None
    spouse_retire_age: int | None = None
    spouse_life_expectancy: int | None = Field(default=85)
    monthly_income: float = Field(default=0, ge=0)
    monthly_expense: float = Field(default=0, ge=0)
    current_assets: float = Field(default=0, ge=0)
    current_liabilities: float = Field(default=0, ge=0)
    monthly_investable: float = Field(default=0, ge=0)
    target_retire_monthly_expense: float = Field(default=0, ge=0)
    existing_insurance_annual: float = Field(default=0, ge=0)


class ClientUpdate(ClientCreate):
    pass


def _upsert_balance_sheet_from_financials(cur, client_id: int, payload: "ClientCreate", force: bool = False) -> None:
    """Sync client financial totals → balance sheet.

    Only writes when the balance sheet has no meaningful data yet (or force=True).
    Maps: monthly_income→salary, current_assets→demand_deposit,
          monthly_expense→living, current_liabilities→mortgage balance.
    Does NOT touch target_retire_monthly_expense.
    """
    if not force:
        cur.execute(
            "SELECT total_assets, total_liabilities, monthly_income FROM client_balance_sheet WHERE client_id=?",
            (client_id,),
        )
        row = cur.fetchone()
        has_data = row and (
            (row["total_assets"] or 0) > 0
            or (row["total_liabilities"] or 0) > 0
            or (row["monthly_income"] or 0) > 0
        )
        if has_data:
            return

    assets = {
        "cash": {"demand_deposit": payload.current_assets or 0, "reserve": 0, "time_deposit": 0, "foreign_currency": 0},
        "investment": {"stocks_funds": 0, "endowment_twd": 0, "other_investment": 0},
        "real_estate": {"house": 0, "land": 0},
        "movable": {"vehicle": 0},
        "income": {"salary": payload.monthly_income or 0, "side_income": 0, "other_income": 0},
    }
    liabilities = {
        "fixed": {
            "mortgage": {"balance": payload.current_liabilities or 0, "monthly_payment": 0},
            "car_loan": {"balance": 0, "monthly_payment": 0},
            "other_loan": {"balance": 0, "monthly_payment": 0},
        },
        "general": {"living": payload.monthly_expense or 0, "rent": 0, "phone": 0, "other": 0},
    }
    summary = compute_summary(assets, liabilities)
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


@router.get("")
@router.get("/")
def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(0, ge=0, le=500),
    include_demo: bool = Query(False),
) -> list[dict[str, Any]] | dict[str, Any]:
    where_sql = "" if include_demo else "WHERE COALESCE(c.is_demo, 0) = 0"
    sql = f"""
        SELECT c.*, f.monthly_income, f.monthly_expense, f.current_assets, f.current_liabilities,
               f.monthly_investable, f.target_retire_monthly_expense, f.existing_insurance_annual
        FROM clients c
        LEFT JOIN client_financials f ON c.id = f.client_id
        {where_sql}
        ORDER BY c.updated_at DESC
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            if limit > 0:
                cur.execute(sql + " LIMIT ? OFFSET ?", (limit, skip))
                rows = [row_to_dict(r) for r in cur.fetchall()]
                cur.execute(f"SELECT COUNT(*) FROM clients c {where_sql}")
                total = cur.fetchone()[0]
                return {"items": rows, "total": total, "skip": skip, "limit": limit}
            cur.execute(sql)
            return [row_to_dict(r) for r in cur.fetchall()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch clients") from exc


@router.get("/{client_id}")
def get_client(client_id: int) -> dict[str, Any]:
    sql = """
        SELECT c.*, f.monthly_income, f.monthly_expense, f.current_assets, f.current_liabilities,
               f.monthly_investable, f.target_retire_monthly_expense, f.existing_insurance_annual
        FROM clients c
        LEFT JOIN client_financials f ON c.id = f.client_id
        WHERE c.id = ?
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (client_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Client not found")
            return row_to_dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch client") from exc


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate) -> dict[str, Any]:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO clients (
                    name, email, phone, age, gender, family_status, children_count, children_ages,
                    occupation, target_retire_age, life_expectancy, risk_tolerance, planning_goals,
                    selected_modules, is_joint_plan, spouse_name, spouse_age, spouse_gender,
                    spouse_retire_age, spouse_life_expectancy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name, payload.email, payload.phone, payload.age,
                    payload.gender, payload.family_status, payload.children_count,
                    json.dumps(payload.children_ages), payload.occupation,
                    payload.target_retire_age, payload.life_expectancy, payload.risk_tolerance,
                    json.dumps(payload.planning_goals), json.dumps(payload.selected_modules),
                    int(payload.is_joint_plan), payload.spouse_name, payload.spouse_age,
                    payload.spouse_gender, payload.spouse_retire_age, payload.spouse_life_expectancy,
                ),
            )
            client_id = cur.lastrowid
            cur.execute(
                """
                INSERT INTO client_financials (
                    client_id, monthly_income, monthly_expense, current_assets, current_liabilities,
                    monthly_investable, target_retire_monthly_expense, existing_insurance_annual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id, payload.monthly_income, payload.monthly_expense,
                    payload.current_assets, payload.current_liabilities,
                    payload.monthly_investable, payload.target_retire_monthly_expense,
                    payload.existing_insurance_annual,
                ),
            )
            # Seed balance sheet from financials (new client has no balance sheet yet)
            _upsert_balance_sheet_from_financials(cur, client_id, payload, force=True)
        return {"id": client_id, "message": "Client created successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to create client") from exc


@router.put("/{client_id}")
def update_client(client_id: int, payload: ClientUpdate) -> dict[str, str]:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE clients SET
                    name=?, email=?, phone=?, age=?, gender=?, family_status=?,
                    children_count=?, children_ages=?, occupation=?, target_retire_age=?,
                    life_expectancy=?, risk_tolerance=?, planning_goals=?, selected_modules=?,
                    is_joint_plan=?, spouse_name=?, spouse_age=?, spouse_gender=?,
                    spouse_retire_age=?, spouse_life_expectancy=?,
                    updated_at=datetime('now')
                WHERE id=?
                """,
                (
                    payload.name, payload.email, payload.phone, payload.age,
                    payload.gender, payload.family_status, payload.children_count,
                    json.dumps(payload.children_ages), payload.occupation,
                    payload.target_retire_age, payload.life_expectancy, payload.risk_tolerance,
                    json.dumps(payload.planning_goals), json.dumps(payload.selected_modules),
                    int(payload.is_joint_plan), payload.spouse_name, payload.spouse_age,
                    payload.spouse_gender, payload.spouse_retire_age, payload.spouse_life_expectancy,
                    client_id,
                ),
            )
            cur.execute(
                """
                INSERT INTO client_financials (
                    client_id, monthly_income, monthly_expense, current_assets, current_liabilities,
                    monthly_investable, target_retire_monthly_expense, existing_insurance_annual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    monthly_income=excluded.monthly_income,
                    monthly_expense=excluded.monthly_expense,
                    current_assets=excluded.current_assets,
                    current_liabilities=excluded.current_liabilities,
                    monthly_investable=excluded.monthly_investable,
                    target_retire_monthly_expense=excluded.target_retire_monthly_expense,
                    existing_insurance_annual=excluded.existing_insurance_annual,
                    updated_at=datetime('now')
                """,
                (
                    client_id, payload.monthly_income, payload.monthly_expense,
                    payload.current_assets, payload.current_liabilities,
                    payload.monthly_investable, payload.target_retire_monthly_expense,
                    payload.existing_insurance_annual,
                ),
            )
            # Sync to balance sheet only when it has no meaningful data
            _upsert_balance_sheet_from_financials(cur, client_id, payload, force=False)
        return {"message": "Client updated successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to update client") from exc


@router.delete("/{client_id}")
def delete_client(client_id: int) -> dict[str, str]:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Client not found")
        return {"message": "Client deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to delete client") from exc
