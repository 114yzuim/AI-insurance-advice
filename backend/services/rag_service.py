from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from services.product_service import get_products

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model: SentenceTransformer | None = None
_product_embeddings: np.ndarray | None = None
_indexed_products: list[dict] | None = None

# Coverage need key → product category
NEEDS_TO_CATEGORY: dict[str, str] = {
    "accident_coverage": "意外傷害",
    "medical_daily": "健康醫療",
    "disability_monthly": "健康醫療",
    "cancer_coverage": "健康醫療",
    "life_coverage": "壽險保障",
}

# Full company name → short aliases users might type
COMPANY_ALIASES: dict[str, list[str]] = {
    "凱基人壽": ["凱基"],
    "台灣人壽": ["台灣人壽", "台壽"],
    "富邦人壽": ["富邦"],
    "新光人壽": ["新光"],
    "遠雄人壽": ["遠雄"],
}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_index() -> tuple[np.ndarray, list[dict]]:
    global _product_embeddings, _indexed_products
    if _product_embeddings is None:
        products = get_products()
        _indexed_products = products
        model = _get_model()
        texts = [
            f"{p['product_name']}，{p['company']}，{p['category']}"
            for p in products
        ]
        _product_embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return _product_embeddings, _indexed_products  # type: ignore[return-value]


def retrieve_relevant_products(query: str, top_k: int = 5) -> list[dict]:
    """Return top_k products most semantically relevant to the query."""
    embeddings, products = _get_index()
    model = _get_model()

    # Company-specific filter: if user names a company, restrict to that company first
    company_filter: str | None = None
    for company, aliases in COMPANY_ALIASES.items():
        if any(alias in query for alias in aliases):
            company_filter = company
            break

    query_vec = model.encode([query], normalize_embeddings=True)[0]
    # Cosine similarity (dot product of L2-normalised vectors)
    scores: np.ndarray = embeddings @ query_vec

    if company_filter:
        indices = [i for i, p in enumerate(products) if p["company"] == company_filter]
        indices.sort(key=lambda i: scores[i], reverse=True)
        return [products[i] for i in indices[:top_k]]

    top_indices = np.argsort(scores)[::-1][:top_k]
    return [products[int(i)] for i in top_indices]


def recommend_products_for_assessment(priority_keys: list[str], top_k: int = 3) -> list[dict]:
    """Return up to top_k products, one per unique target category in priority order."""
    products = get_products()
    seen_cats: set[str] = set()
    result: list[dict] = []

    for key in priority_keys:
        if len(result) >= top_k:
            break
        cat = NEEDS_TO_CATEGORY.get(key)
        if not cat or cat in seen_cats:
            continue
        seen_cats.add(cat)
        cat_prods = [p for p in products if p["category"] == cat]
        if cat_prods:
            result.append(cat_prods[0])

    return result


def format_context(products: list[dict]) -> str:
    if not products:
        return ""

    lines = [
        "【資料庫參考商品】以下是從商品資料庫中語意檢索到的相關保險商品：",
        "",
    ]
    for p in products:
        lines.append(
            f"• {p['product_name']}｜{p['company']}｜{p['category']}｜{p['currency']}"
        )
    lines.append("")
    return "\n".join(lines)
