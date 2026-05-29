from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from services.needs_assessment_service import get_family_assessment

router = APIRouter()

DISCLAIMER = "本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。"


class MemberInput(BaseModel):
    name: str
    answers: dict


class FamilyAssessmentRequest(BaseModel):
    members: List[MemberInput]


class RecommendationItem(BaseModel):
    key: str
    priority: int
    amount: int
    unit: str
    premium_range: str
    monthly_premium_mid: int
    within_budget: bool
    reason: str


class ProductCard(BaseModel):
    product_id: str
    product_name: str
    company: str
    category: str
    source_url: str = ""


class MemberAssessment(BaseModel):
    name: str
    items: List[RecommendationItem]
    budget_note: str
    summary: str
    recommended_products: List[ProductCard] = []


class FamilyAssessmentResponse(BaseModel):
    family_summary: str
    members: List[MemberAssessment]
    disclaimer: str


@router.post("", response_model=FamilyAssessmentResponse)
async def needs_assessment(req: FamilyAssessmentRequest):
    members_input = [{"name": m.name, "answers": m.answers} for m in req.members]
    result = await get_family_assessment(members_input)

    members_out = []
    for m in result.get("members", []):
        members_out.append(
            MemberAssessment(
                name=m.get("name", ""),
                items=[RecommendationItem(**item) for item in m.get("items", [])],
                budget_note=m.get("budget_note", ""),
                summary=m.get("summary", ""),
                recommended_products=[
                    ProductCard(**p) for p in m.get("recommended_products", [])
                ],
            )
        )

    return FamilyAssessmentResponse(
        family_summary=result.get("family_summary", ""),
        members=members_out,
        disclaimer=DISCLAIMER,
    )
