from typing import List
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from services.pdf_service import extract_pdf_from_bytes
from services.policy_extraction_service import (
    extract_policy_coverage,
    build_gaps,
    BASELINES,
)

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。"


class PolicyCoverage(BaseModel):
    policy_name: str
    company: str
    life_coverage: int
    medical_daily: int
    accident_coverage: int
    cancer_coverage: int
    disability_monthly: int
    notes: str


class HealthCheckResponse(BaseModel):
    policies: List[PolicyCoverage]
    summary: dict
    baselines: dict
    gaps: List[str]
    disclaimer: str


@router.post("", response_model=HealthCheckResponse)
async def health_check(files: List[UploadFile] = File(...)):
    policies = []
    for file in files[:5]:
        content = await file.read()
        text = await extract_pdf_from_bytes(content)
        if text.strip():
            data = await extract_policy_coverage(text)
            policies.append(PolicyCoverage(**data))

    summary = {
        "life_coverage": sum(p.life_coverage for p in policies),
        "medical_daily": sum(p.medical_daily for p in policies),
        "accident_coverage": sum(p.accident_coverage for p in policies),
        "cancer_coverage": sum(p.cancer_coverage for p in policies),
        "disability_monthly": sum(p.disability_monthly for p in policies),
    }

    return HealthCheckResponse(
        policies=policies,
        summary=summary,
        baselines=BASELINES,
        gaps=build_gaps(summary),
        disclaimer=DISCLAIMER,
    )
