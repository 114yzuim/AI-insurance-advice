from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from psycopg2.extras import Json

from app.api.schemas import ClientCreate, ClientUpdate
from app.db import get_connection

router = APIRouter()


@router.get("")
@router.get("/")
def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(0, ge=0, le=500),
    include_demo: bool = Query(False),
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return clients, optionally paginated.

    * ``/api/clients``                         → active client list (array)
    * ``/api/clients?include_demo=1``           → include the reusable demo client
    * ``/api/clients?limit=20&include_demo=1``  → ``{items, total, skip, limit}``
    """
    where_sql = "" if include_demo else "WHERE COALESCE(c.is_demo, false) = false"
    base_sql = """
      SELECT c.*, f.monthly_income, f.monthly_expense, f.current_assets, f.current_liabilities,
             f.monthly_investable, f.target_retire_monthly_expense, f.existing_insurance_annual
      FROM clients c
      LEFT JOIN client_financials f ON c.id = f.client_id
      {where_sql}
      ORDER BY c.updated_at DESC
    """.format(where_sql=where_sql)
    count_sql = f"SELECT COUNT(*) AS total FROM clients c {where_sql}"
    try:
        with get_connection() as conn, conn.cursor() as cur:
            if limit > 0:
                cur.execute(base_sql + " LIMIT %s OFFSET %s", (limit, skip))
                rows = cur.fetchall()
                cur.execute(count_sql)
                total = cur.fetchone()["total"]
                return {"items": rows, "total": total, "skip": skip, "limit": limit}
            cur.execute(base_sql)
            return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch clients") from exc


@router.get("/{client_id}")
def get_client(client_id: int) -> dict[str, Any]:
    sql = """
      SELECT c.*, f.monthly_income, f.monthly_expense, f.current_assets, f.current_liabilities,
             f.monthly_investable, f.target_retire_monthly_expense, f.existing_insurance_annual
      FROM clients c
      LEFT JOIN client_financials f ON c.id = f.client_id
      WHERE c.id = %s
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (client_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Client not found")
            return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch client") from exc


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate) -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                          INSERT INTO clients (
                            user_id, name, email, phone, age, gender, family_status, children_count, children_ages, occupation,
                            target_retire_age, life_expectancy, risk_tolerance, planning_goals, selected_modules,
                            is_joint_plan, spouse_name, spouse_age, spouse_gender, spouse_retire_age, spouse_life_expectancy
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                          RETURNING id
                        """,
                        (
                            1,
                            payload.name,
                            payload.email,
                            payload.phone,
                            payload.age,
                            payload.gender,
                            payload.family_status,
                            payload.children_count,
                            Json(payload.children_ages),
                            payload.occupation,
                            payload.target_retire_age,
                            payload.life_expectancy,
                            payload.risk_tolerance,
                            Json(payload.planning_goals),
                            payload.selected_modules,
                            payload.is_joint_plan,
                            payload.spouse_name,
                            payload.spouse_age,
                            payload.spouse_gender,
                            payload.spouse_retire_age,
                            payload.spouse_life_expectancy,
                        ),
                    )
                    client_id = int(cur.fetchone()["id"])

                    cur.execute(
                        """
                          INSERT INTO client_financials (
                            client_id, monthly_income, monthly_expense, current_assets, current_liabilities,
                            monthly_investable, target_retire_monthly_expense, existing_insurance_annual
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            client_id,
                            payload.monthly_income,
                            payload.monthly_expense,
                            payload.current_assets,
                            payload.current_liabilities,
                            payload.monthly_investable,
                            payload.target_retire_monthly_expense,
                            payload.existing_insurance_annual,
                        ),
                    )

        return {"id": client_id, "message": "Client created successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to create client") from exc


@router.put("/{client_id}")
def update_client(client_id: int, payload: ClientUpdate) -> dict[str, str]:
    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                          UPDATE clients
                          SET
                            name = %s,
                            email = %s,
                            phone = %s,
                            age = %s,
                            gender = %s,
                            family_status = %s,
                            children_count = %s,
                            children_ages = %s,
                            occupation = %s,
                            target_retire_age = %s,
                            life_expectancy = %s,
                            risk_tolerance = %s,
                            planning_goals = %s,
                            selected_modules = %s,
                            is_joint_plan = %s,
                            spouse_name = %s,
                            spouse_age = %s,
                            spouse_gender = %s,
                            spouse_retire_age = %s,
                            spouse_life_expectancy = %s,
                            updated_at = CURRENT_TIMESTAMP
                          WHERE id = %s
                        """,
                        (
                            payload.name,
                            payload.email,
                            payload.phone,
                            payload.age,
                            payload.gender,
                            payload.family_status,
                            payload.children_count,
                            Json(payload.children_ages),
                            payload.occupation,
                            payload.target_retire_age,
                            payload.life_expectancy,
                            payload.risk_tolerance,
                            Json(payload.planning_goals),
                            payload.selected_modules,
                            payload.is_joint_plan,
                            payload.spouse_name,
                            payload.spouse_age,
                            payload.spouse_gender,
                            payload.spouse_retire_age,
                            payload.spouse_life_expectancy,
                            client_id,
                        ),
                    )

                    cur.execute(
                        """
                          INSERT INTO client_financials (
                            client_id, monthly_income, monthly_expense, current_assets, current_liabilities,
                            monthly_investable, target_retire_monthly_expense, existing_insurance_annual
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                          ON CONFLICT (client_id) DO UPDATE SET
                            monthly_income = EXCLUDED.monthly_income,
                            monthly_expense = EXCLUDED.monthly_expense,
                            current_assets = EXCLUDED.current_assets,
                            current_liabilities = EXCLUDED.current_liabilities,
                            monthly_investable = EXCLUDED.monthly_investable,
                            target_retire_monthly_expense = EXCLUDED.target_retire_monthly_expense,
                            existing_insurance_annual = EXCLUDED.existing_insurance_annual,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            client_id,
                            payload.monthly_income,
                            payload.monthly_expense,
                            payload.current_assets,
                            payload.current_liabilities,
                            payload.monthly_investable,
                            payload.target_retire_monthly_expense,
                            payload.existing_insurance_annual,
                        ),
                    )

        return {"message": "Client updated successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to update client") from exc


@router.delete("/{client_id}")
def delete_client(client_id: int) -> dict[str, str]:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM clients WHERE id = %s RETURNING id", (client_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Client not found")
        return {"message": "Client deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to delete client") from exc

