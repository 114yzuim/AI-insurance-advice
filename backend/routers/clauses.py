from fastapi import APIRouter, Query
from services.clause_service import inventory_clause_summary, search_clauses

router = APIRouter()


@router.get("/summary")
def clause_summary():
    return inventory_clause_summary()


@router.get("/search")
def clause_search(
    q: str = Query(..., min_length=1),
    company: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    return {"items": search_clauses(q, company=company, category=category, limit=limit)}
