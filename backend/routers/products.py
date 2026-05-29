from fastapi import APIRouter, Query
from services.product_service import get_products, search_products

router = APIRouter()


@router.get("")
def list_products(
    category: str | None = Query(None),
    company: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    results = search_products(category=category, company=company, keyword=keyword)
    start = (page - 1) * page_size
    return {
        "total": len(results),
        "page": page,
        "page_size": page_size,
        "products": results[start : start + page_size],
    }


@router.get("/categories")
def list_categories():
    products = get_products()
    cats = sorted({p["category"] for p in products})
    categories = [c for c in cats if c != "其他"] + (["其他"] if "其他" in cats else [])
    return {"categories": categories}


@router.get("/companies")
def list_companies():
    products = get_products()
    companies = sorted({p["company"] for p in products})
    return {"companies": companies}


@router.get("/{product_id}")
def get_product(product_id: str):
    products = get_products()
    for p in products:
        if p["product_id"] == product_id:
            return p
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Product not found")
