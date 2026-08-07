import json
from typing import Any

from fastapi import APIRouter, HTTPException

from db import get_connection, row_to_dict

router = APIRouter()


@router.get("/{client_id}")
def get_questionnaire(client_id: int) -> dict[str, Any] | None:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM client_questionnaires WHERE client_id = ?", (client_id,))
            row = cur.fetchone()
            return row_to_dict(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch questionnaire") from exc


@router.put("/{client_id}")
def upsert_questionnaire(client_id: int, payload: dict[str, Any]) -> dict[str, str]:
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO client_questionnaires (
                    client_id, preferred_channels, retire_income_sources, retire_dreams,
                    retire_target_amount, retire_monthly_living, interested_topics,
                    monthly_investable_budget, risk_factors, consent_advisory,
                    has_existing_insurance, existing_policies_notes,
                    health_status, has_family_disease, existing_medical_coverage, existing_ltc_coverage,
                    has_existing_life_insurance, has_existing_medical_insurance,
                    has_existing_accident_insurance, has_existing_annuity, has_existing_savings_insurance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET
                    preferred_channels=excluded.preferred_channels,
                    retire_income_sources=excluded.retire_income_sources,
                    retire_dreams=excluded.retire_dreams,
                    retire_target_amount=excluded.retire_target_amount,
                    retire_monthly_living=excluded.retire_monthly_living,
                    interested_topics=excluded.interested_topics,
                    monthly_investable_budget=excluded.monthly_investable_budget,
                    risk_factors=excluded.risk_factors,
                    consent_advisory=excluded.consent_advisory,
                    has_existing_insurance=excluded.has_existing_insurance,
                    existing_policies_notes=excluded.existing_policies_notes,
                    health_status=excluded.health_status,
                    has_family_disease=excluded.has_family_disease,
                    existing_medical_coverage=excluded.existing_medical_coverage,
                    existing_ltc_coverage=excluded.existing_ltc_coverage,
                    has_existing_life_insurance=excluded.has_existing_life_insurance,
                    has_existing_medical_insurance=excluded.has_existing_medical_insurance,
                    has_existing_accident_insurance=excluded.has_existing_accident_insurance,
                    has_existing_annuity=excluded.has_existing_annuity,
                    has_existing_savings_insurance=excluded.has_existing_savings_insurance,
                    updated_at=datetime('now')
                """,
                (
                    client_id,
                    json.dumps(payload.get("preferred_channels") or []),
                    json.dumps(payload.get("retire_income_sources") or []),
                    json.dumps(payload.get("retire_dreams") or []),
                    payload.get("retire_target_amount") or 0,
                    payload.get("retire_monthly_living") or 0,
                    json.dumps(payload.get("interested_topics") or []),
                    payload.get("monthly_investable_budget") or 0,
                    json.dumps(payload.get("risk_factors") or []),
                    int(bool(payload.get("consent_advisory", True))),
                    int(bool(payload.get("has_existing_insurance", False))),
                    payload.get("existing_policies_notes") or "",
                    payload.get("health_status") or "良好",
                    int(bool(payload.get("has_family_disease", False))),
                    payload.get("existing_medical_coverage") or "不清楚",
                    payload.get("existing_ltc_coverage") or "不清楚",
                    int(bool(payload.get("has_existing_life_insurance"))),
                    int(bool(payload.get("has_existing_medical_insurance"))),
                    int(bool(payload.get("has_existing_accident_insurance"))),
                    int(bool(payload.get("has_existing_annuity"))),
                    int(bool(payload.get("has_existing_savings_insurance"))),
                ),
            )
            # sync monthly_investable_budget → client_financials
            budget = payload.get("monthly_investable_budget")
            if budget and float(budget) > 0:
                cur.execute(
                    """
                    INSERT INTO client_financials (client_id, monthly_investable)
                    VALUES (?, ?)
                    ON CONFLICT(client_id) DO UPDATE SET
                        monthly_investable=excluded.monthly_investable,
                        updated_at=datetime('now')
                    """,
                    (client_id, budget),
                )
            retire_monthly = payload.get("retire_monthly_living")
            if retire_monthly and float(retire_monthly) > 0:
                cur.execute(
                    """
                    UPDATE client_financials
                    SET target_retire_monthly_expense=?, updated_at=datetime('now')
                    WHERE client_id=?
                    """,
                    (retire_monthly, client_id),
                )
            cur.execute(
                """
                UPDATE clients SET status='questionnaire_done', updated_at=datetime('now')
                WHERE id=? AND status='new'
                """,
                (client_id,),
            )
        return {"message": "Questionnaire saved successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save questionnaire") from exc
