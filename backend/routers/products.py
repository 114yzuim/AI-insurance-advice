from fastapi import APIRouter, HTTPException, Query
from services.product_service import (
    get_product_by_id,
    get_product_inventory_summary,
    list_categories,
    list_companies,
    query_products,
)

router = APIRouter()


@router.get("")
def list_products(
    category: str | None = Query(None),
    company: str | None = Query(None),
    keyword: str | None = Query(None),
    status: str | None = Query(None, description="active | discontinued | unknown"),
    coverage_type: str | None = Query(
        None, description="life | cancer | critical | accident | daily | medical | ltc (from extracted clause facts)"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, products = query_products(
        category=category, company=company, keyword=keyword, status=status, coverage_type=coverage_type,
        page=page, page_size=page_size,
    )
    return {"total": total, "page": page, "page_size": page_size, "products": products}


@router.get("/categories")
def categories():
    return {"categories": list_categories()}


@router.get("/companies")
def companies():
    return {"companies": list_companies()}


@router.get("/inventory-summary")
def inventory_summary():
    return get_product_inventory_summary()


@router.get("/{product_id}")
def get_product(product_id: str):
    product = get_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
