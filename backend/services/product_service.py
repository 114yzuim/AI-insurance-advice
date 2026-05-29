import json
from pathlib import Path
from functools import lru_cache

DATA_PATH = Path(__file__).parent.parent / "data" / "crawled_products_with_pdf_dm_links.json"


@lru_cache(maxsize=1)
def get_products() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def search_products(
    category: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = get_products()
    if category:
        results = [p for p in results if p["category"] == category]
    if company:
        results = [p for p in results if p["company"] == company]
    if keyword:
        kw = keyword.lower()
        results = [p for p in results if kw in p["product_name"].lower()]
    return results
