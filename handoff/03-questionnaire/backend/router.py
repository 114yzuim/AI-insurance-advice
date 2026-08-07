from typing import Any

from fastapi import APIRouter, HTTPException
from psycopg2.extras import Json

from app.db import get_connection

router = APIRouter()


@router.get("/{client_id}")
def get_questionnaire(client_id: int) -> dict[str, Any] | None:
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM client_questionnaires WHERE client_id = %s", (client_id,))
            row = cur.fetchone()
            return row if row else None
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch questionnaire") from exc


@router.put("/{client_id}")
def upsert_questionnaire(client_id: int, payload: dict[str, Any]) -> dict[str, str]:
    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
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
                          )
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                          ON CONFLICT (client_id) DO UPDATE SET
                            preferred_channels = EXCLUDED.preferred_channels,
                            retire_income_sources = EXCLUDED.retire_income_sources,
                            retire_dreams = EXCLUDED.retire_dreams,
                            retire_target_amount = EXCLUDED.retire_target_amount,
                            retire_monthly_living = EXCLUDED.retire_monthly_living,
                            interested_topics = EXCLUDED.interested_topics,
                            monthly_investable_budget = EXCLUDED.monthly_investable_budget,
                            risk_factors = EXCLUDED.risk_factors,
                            consent_advisory = EXCLUDED.consent_advisory,
                            has_existing_insurance = EXCLUDED.has_existing_insurance,
                            existing_policies_notes = EXCLUDED.existing_policies_notes,
                            health_status = EXCLUDED.health_status,
                            has_family_disease = EXCLUDED.has_family_disease,
                            existing_medical_coverage = EXCLUDED.existing_medical_coverage,
                            existing_ltc_coverage = EXCLUDED.existing_ltc_coverage,
                            has_existing_life_insurance = EXCLUDED.has_existing_life_insurance,
                            has_existing_medical_insurance = EXCLUDED.has_existing_medical_insurance,
                            has_existing_accident_insurance = EXCLUDED.has_existing_accident_insurance,
                            has_existing_annuity = EXCLUDED.has_existing_annuity,
                            has_existing_savings_insurance = EXCLUDED.has_existing_savings_insurance,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            client_id,
                            Json(payload.get("preferred_channels") or []),
                            Json(payload.get("retire_income_sources") or []),
                            Json(payload.get("retire_dreams") or []),
                            payload.get("retire_target_amount") or 0,
                            payload.get("retire_monthly_living") or 0,
                            Json(payload.get("interested_topics") or []),
                            payload.get("monthly_investable_budget") or 0,
                            Json(payload.get("risk_factors") or []),
                            payload.get("consent_advisory") if payload.get("consent_advisory") is not None else True,
                            payload.get("has_existing_insurance")
                            if payload.get("has_existing_insurance") is not None
                            else False,
                            payload.get("existing_policies_notes") or "",
                            payload.get("health_status"),
                            payload.get("has_family_disease"),
                            payload.get("existing_medical_coverage"),
                            payload.get("existing_ltc_coverage"),
                            bool(payload.get("has_existing_life_insurance")),
                            bool(payload.get("has_existing_medical_insurance")),
                            bool(payload.get("has_existing_accident_insurance")),
                            bool(payload.get("has_existing_annuity")),
                            bool(payload.get("has_existing_savings_insurance")),
                        ),
                    )

                    monthly_budget = payload.get("monthly_investable_budget")
                    if monthly_budget and float(monthly_budget) > 0:
                        cur.execute(
                            """
                              INSERT INTO client_financials (client_id, monthly_investable)
                              VALUES (%s, %s)
                              ON CONFLICT (client_id) DO UPDATE SET
                                monthly_investable = EXCLUDED.monthly_investable,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (client_id, monthly_budget),
                        )

                    retire_monthly = payload.get("retire_monthly_living")
                    if retire_monthly and float(retire_monthly) > 0:
                        cur.execute(
                            """
                              UPDATE client_financials
                              SET target_retire_monthly_expense = %s, updated_at = CURRENT_TIMESTAMP
                              WHERE client_id = %s
                            """,
                            (retire_monthly, client_id),
                        )

                    cur.execute(
                        """
                          UPDATE clients
                          SET status = 'questionnaire_done', updated_at = CURRENT_TIMESTAMP
                          WHERE id = %s AND status = 'new'
                        """,
                        (client_id,),
                    )

        return {"message": "Questionnaire saved successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save questionnaire") from exc



