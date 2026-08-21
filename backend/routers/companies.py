from fastapi import APIRouter, Query
from pydantic import BaseModel
from services.company_service import list_companies, upsert_company

router = APIRouter()


class CompanyPayload(BaseModel):
    slug: str
    name: str
    short_name: str
    type: str
    status: str = "active"
    former_names: list[str] = []
    official_url: str = ""
    source_url: str = ""


@router.get("")
def companies(company_type: str | None = Query(None, alias="type")):
    return {"companies": list_companies(company_type)}


@router.post("")
def save_company(payload: CompanyPayload):
    return upsert_company(payload.model_dump())
