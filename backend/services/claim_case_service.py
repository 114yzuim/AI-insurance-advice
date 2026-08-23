from __future__ import annotations

import json
from typing import Any

from inventory_db import get_inventory_connection
from services.policy_service import DEFAULT_PROFILE_ID, ensure_default_profile

CLAIM_CASE_STATUSES = {
    "文件整理中",
    "待送件",
    "已送件",
    "保險公司審核中",
    "已補件",
    "已結案",
}

JSON_FIELDS = {"document_summary", "required_documents", "companies"}


def list_claim_cases(profile_id: str = DEFAULT_PROFILE_ID, client_id: str = "") -> list[dict[str, Any]]:
    ensure_default_profile()
    clauses: list[str] = []
    params: list[Any] = []
    if profile_id and profile_id != "all":
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if client_id:
        clauses.append("client_id = ?")
        params.append(client_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_inventory_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM claim_cases
            {where_sql}
            ORDER BY datetime(updated_at) DESC, id DESC
            """,
            params,
        ).fetchall()
        return [claim_case_to_dict(row) for row in rows]


def create_claim_case(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_default_profile()
    profile_id = (payload.get("profile_id") or DEFAULT_PROFILE_ID).strip()
    status = normalize_status(payload.get("status") or "文件整理中")
    with get_inventory_connection() as conn:
        ensure_profile_row(conn, profile_id, payload)
        cursor = conn.execute(
            """
            INSERT INTO claim_cases (
                profile_id, client_id, owner_name, scenario, status,
                medical_expense_total, estimated_total, high_confidence_total, review_total,
                document_summary, required_documents, companies,
                notes, next_follow_up_date, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                profile_id,
                str(payload.get("client_id") or ""),
                str(payload.get("owner_name") or ""),
                str(payload.get("scenario") or ""),
                status,
                float(payload.get("medical_expense_total") or 0),
                float(payload.get("estimated_total") or 0),
                float(payload.get("high_confidence_total") or 0),
                float(payload.get("review_total") or 0),
                dumps_json(payload.get("document_summary") or {}),
                dumps_json(payload.get("required_documents") or []),
                dumps_json(payload.get("companies") or []),
                str(payload.get("notes") or ""),
                str(payload.get("next_follow_up_date") or ""),
            ),
        )
        row = conn.execute("SELECT * FROM claim_cases WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
        return claim_case_to_dict(row)


def update_claim_case(case_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    ensure_default_profile()
    allowed = {
        "status",
        "notes",
        "next_follow_up_date",
        "medical_expense_total",
        "estimated_total",
        "high_confidence_total",
        "review_total",
    }
    updates: list[str] = []
    params: list[Any] = []

    for key in allowed:
        if key not in payload:
            continue
        value = payload[key]
        if key == "status":
            value = normalize_status(value)
        if key.endswith("_total"):
            value = float(value or 0)
        updates.append(f"{key} = ?")
        params.append(value)

    if not updates:
        return get_claim_case(case_id)

    updates.append("updated_at = datetime('now')")
    params.append(case_id)

    with get_inventory_connection() as conn:
        cursor = conn.execute(
            f"UPDATE claim_cases SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM claim_cases WHERE id = ?", (case_id,)).fetchone()
        return claim_case_to_dict(row)


def get_claim_case(case_id: int) -> dict[str, Any] | None:
    ensure_default_profile()
    with get_inventory_connection() as conn:
        row = conn.execute("SELECT * FROM claim_cases WHERE id = ?", (case_id,)).fetchone()
        return claim_case_to_dict(row) if row else None


def normalize_status(status: Any) -> str:
    value = str(status or "").strip()
    return value if value in CLAIM_CASE_STATUSES else "文件整理中"


def ensure_profile_row(conn, profile_id: str, payload: dict[str, Any]) -> None:
    owner_name = str(payload.get("owner_name") or "理賠客戶").strip() or "理賠客戶"
    conn.execute(
        """
        INSERT INTO insurance_profiles (id, owner_name, relation, updated_at)
        VALUES (?, ?, '本人', datetime('now'))
        ON CONFLICT(id) DO NOTHING
        """,
        (profile_id, owner_name),
    )


def claim_case_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["id"] = int(data["id"])
    for field in JSON_FIELDS:
        data[field] = loads_json(data.get(field), [] if field != "document_summary" else {})
    return data


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads_json(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
