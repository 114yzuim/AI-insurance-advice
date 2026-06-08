from __future__ import annotations

import pathlib

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from services.product_service import get_products

_MODEL_NAME = "BAAI/bge-m3"
_DB_PATH = str(pathlib.Path(__file__).parent.parent / "chroma_db")
_COLLECTION_NAME = "insurance_products"
_RRF_K = 60  # RRF constant — higher = flatter score distribution

_model: SentenceTransformer | None = None
_collection = None
_bm25: BM25Okapi | None = None
_bm25_products: list[dict] | None = None

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


def _tokenize(text: str) -> list[str]:
    """Character-level tokenization: each Chinese character + alphanumeric tokens."""
    return [c for c in text if "一" <= c <= "鿿" or c.isalnum()]


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _build_index(col) -> None:
    """Embed all 780 products and store in ChromaDB."""
    products = get_products()
    model = _get_model()
    texts = [
        f"{p['product_name']}，{p['company']}，{p['category']}"
        for p in products
    ]
    embeddings = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    ).tolist()
    col.add(
        ids=[str(i) for i in range(len(products))],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "product_name": p["product_name"],
                "company": p["company"],
                "category": p["category"],
                "currency": p.get("currency", ""),
            }
            for p in products
        ],
    )


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    client = chromadb.PersistentClient(path=_DB_PATH)

    # Auto-rebuild if index was built with a different embedding model
    try:
        existing = client.get_collection(_COLLECTION_NAME)
        if existing.metadata.get("model_name") != _MODEL_NAME:
            client.delete_collection(_COLLECTION_NAME)
    except Exception:
        pass

    col = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "model_name": _MODEL_NAME},
    )
    if col.count() == 0:
        _build_index(col)

    _collection = col
    return _collection


def _get_bm25() -> tuple[BM25Okapi, list[dict]]:
    global _bm25, _bm25_products
    if _bm25 is not None:
        return _bm25, _bm25_products  # type: ignore[return-value]

    products = get_products()
    _bm25_products = products
    texts = [
        f"{p['product_name']}，{p['company']}，{p['category']}"
        for p in products
    ]
    _bm25 = BM25Okapi([_tokenize(t) for t in texts])
    return _bm25, _bm25_products


def retrieve_relevant_products(query: str, top_k: int = 5) -> list[dict]:
    """Hybrid retrieval: vector search (BGE-M3) + BM25 merged via Reciprocal Rank Fusion."""
    candidate_k = min(top_k * 4, 20)

    # Company filter detection
    company_filter: str | None = None
    for company, aliases in COMPANY_ALIASES.items():
        if any(alias in query for alias in aliases):
            company_filter = company
            break

    # --- Vector search (ChromaDB) ---
    col = _get_collection()
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0].tolist()

    vec_kwargs: dict = {
        "query_embeddings": [query_vec],
        "n_results": candidate_k,
        "include": ["metadatas"],
    }
    if company_filter:
        vec_kwargs["where"] = {"company": company_filter}

    try:
        vec_results = col.query(**vec_kwargs)
    except Exception:
        vec_kwargs.pop("where", None)
        vec_results = col.query(**vec_kwargs)

    vector_ids: list[str] = vec_results["ids"][0]
    vector_metas: list[dict] = vec_results["metadatas"][0]

    # --- BM25 search ---
    bm25, products = _get_bm25()
    bm25_scores = bm25.get_scores(_tokenize(query))

    if company_filter:
        candidate_indices = [i for i, p in enumerate(products) if p["company"] == company_filter]
    else:
        candidate_indices = list(range(len(products)))

    bm25_top = sorted(candidate_indices, key=lambda i: bm25_scores[i], reverse=True)[:candidate_k]

    # --- Reciprocal Rank Fusion ---
    rrf: dict[str, float] = {}
    id_to_meta: dict[str, dict] = {}

    for rank, vid in enumerate(vector_ids):
        rrf[vid] = rrf.get(vid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        id_to_meta[vid] = vector_metas[rank]

    for rank, idx in enumerate(bm25_top):
        sid = str(idx)
        rrf[sid] = rrf.get(sid, 0.0) + 1.0 / (_RRF_K + rank + 1)
        if sid not in id_to_meta:
            p = products[idx]
            id_to_meta[sid] = {
                "product_name": p["product_name"],
                "company": p["company"],
                "category": p["category"],
                "currency": p.get("currency", ""),
            }

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:top_k]
    return [id_to_meta[sid] for sid in sorted_ids]


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
            f"• {p['product_name']}｜{p['company']}｜{p['category']}｜{p.get('currency', '')}"
        )
    lines.append("")
    return "\n".join(lines)
