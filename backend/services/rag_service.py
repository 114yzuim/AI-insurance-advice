"""Product retrieval for the AI advisor.

Product vectors are computed OFFLINE by scripts/build_product_embeddings.py
(on the operator's PC) and pushed to Postgres by scripts/sync_to_production.py
into product_embeddings (pgvector). At request time this module only embeds
the user's query and asks the database for the nearest products -- nothing
is indexed at startup, and the ~130k-product catalogue is never loaded into
memory. (It used to embed every product into ChromaDB on first use, which is
hours of CPU at this catalogue size.)

Locally (SQLite, no pgvector) the same vectors are read from
backend/data/product_embeddings/ and searched with numpy.
"""

from __future__ import annotations

import json
import pathlib
import re
import unicodedata

import numpy as np
from sentence_transformers import SentenceTransformer

from inventory_db import get_inventory_connection, row_to_dict
from services.product_service import list_companies, load_attributes

_MODEL_NAME = "BAAI/bge-m3"  # must match scripts/build_product_embeddings.py
_LOCAL_EMBEDDINGS_DIR = pathlib.Path(__file__).parent.parent / "data" / "product_embeddings"

_model: SentenceTransformer | None = None
_local_index: tuple[np.ndarray, np.ndarray] | None = None  # (ids, vectors)

# Coverage need key → product category
NEEDS_TO_CATEGORY: dict[str, str] = {
    "accident_coverage": "意外傷害",
    "medical_daily": "健康醫療",
    "disability_monthly": "健康醫療",
    "cancer_coverage": "健康醫療",
    "life_coverage": "壽險保障",
}

# Short aliases users might type → company. Brands shared by a life and a
# property company resolve to the life company (the advisor's main use).
COMPANY_ALIASES: dict[str, list[str]] = {
    "凱基人壽": ["凱基"],
    "台灣人壽": ["台灣人壽", "台壽"],
    "富邦人壽": ["富邦"],
    "新光人壽": ["新光"],
    "遠雄人壽": ["遠雄"],
    "國泰人壽": ["國泰"],
    "南山人壽": ["南山"],
    "三商美邦人壽": ["三商美邦", "三商"],
    "全球人壽": ["全球人壽"],
    "法國巴黎人壽": ["法國巴黎", "法巴"],
}

# Filing revisions of one product ("(第3次部分變更)") -- collapsed in results
# so five revisions of the same product don't fill the whole top-k.
_REVISION_RE = re.compile(r"[(（]\s*第?\s*[0-9一二三四五六七八九十百]+\s*次\s*部[分份]變更\s*[)）]")


def _base_name(name: str) -> str:
    return _REVISION_RE.sub("", unicodedata.normalize("NFKC", name or "")).strip()


_RESULT_COLUMNS = "p.id, p.product_name, p.company_name AS company, p.category, p.currency, p.status, p.source"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _encode(text: str) -> np.ndarray:
    return _get_model().encode([text], normalize_embeddings=True)[0].astype(np.float32)


def _detect_company(query: str) -> str | None:
    # Exact company names first (longest wins: 中國信託產物 over 中國信託人壽…),
    # then the short aliases.
    for name in sorted(list_companies(), key=len, reverse=True):
        if name != "公司未知" and name in query:
            return name
    for company, aliases in COMPANY_ALIASES.items():
        if any(alias in query for alias in aliases):
            return company
    return None


def _filters(query: str, company: str | None) -> tuple[list[str], list]:
    where, params = [], []
    # Recommend products that are on sale unless the user asks about
    # discontinued ones -- ~94k of the TII products are 停售.
    if "停售" not in query:
        where.append("p.status <> 'discontinued'")
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    return where, params


def _search_postgres(conn, query_vec: np.ndarray, where: list[str], params: list, k: int) -> list[dict]:
    vec = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    # iterative_scan lets the HNSW index keep scanning when the WHERE filter
    # (on-sale only / one company) discards most nearest neighbours; the
    # MATERIALIZED CTE re-sorts, since relaxed_order may return them slightly
    # out of order (see pgvector docs).
    conn.execute("SET LOCAL hnsw.ef_search = 100")
    conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
    rows = conn.execute(
        f"""
        WITH nearest AS MATERIALIZED (
            SELECT {_RESULT_COLUMNS}, e.embedding <=> ?::halfvec AS distance
            FROM product_embeddings e
            JOIN insurance_products p ON p.id = e.product_db_id
            {where_sql}
            ORDER BY distance
            LIMIT ?
        )
        SELECT * FROM nearest ORDER BY distance
        """,
        [vec, *params, k],
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def _load_local_index() -> tuple[np.ndarray, np.ndarray]:
    global _local_index
    if _local_index is None:
        meta = json.loads((_LOCAL_EMBEDDINGS_DIR / "meta.json").read_text(encoding="utf-8"))
        vectors = np.load(_LOCAL_EMBEDDINGS_DIR / "embeddings.npy")
        valid = np.array([bool(h) for h in meta["text_hashes"]])
        _local_index = (np.array(meta["ids"])[valid], vectors[valid])
    return _local_index


def _search_local(conn, query_vec: np.ndarray, where: list[str], params: list, k: int) -> list[dict]:
    ids, vectors = _load_local_index()
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    allowed = {r[0] for r in conn.execute(f"SELECT p.id FROM insurance_products p {where_sql}", params).fetchall()}
    mask = np.fromiter((i in allowed for i in ids), dtype=bool, count=len(ids))
    if not mask.any():
        return []
    cand_ids, cand_vecs = ids[mask], vectors[mask]
    scores = cand_vecs.astype(np.float32) @ query_vec
    top = np.argsort(-scores)[:k]
    top_ids = [int(cand_ids[i]) for i in top]
    placeholders = ", ".join("?" for _ in top_ids)
    rows = {r[0]: row_to_dict(r) for r in conn.execute(
        f"SELECT {_RESULT_COLUMNS} FROM insurance_products p WHERE p.id IN ({placeholders})", top_ids
    ).fetchall()}
    return [rows[i] for i in top_ids if i in rows]


def retrieve_relevant_products(query: str, top_k: int = 5) -> list[dict]:
    """Nearest products to the query by BGE-M3 embedding, on-sale only by
    default, restricted to a company if the query names one."""
    company = _detect_company(query)
    query_vec = _encode(query)
    candidate_k = top_k * 6  # headroom for collapsing revisions below
    with get_inventory_connection() as conn:
        search = _search_postgres if getattr(conn, "dialect", "sqlite") == "postgres" else _search_local
        where, params = _filters(query, company)
        candidates = search(conn, query_vec, where, params, candidate_k)
        if not candidates and company:  # company named but nothing matched -> widen
            where, params = _filters(query, None)
            candidates = search(conn, query_vec, where, params, candidate_k)
        # Clause facts (scripts/extract_product_attributes.py) for the
        # context the LLM sees -- coverage types, benefits, waiting periods,
        # exclusions -- instead of just a product name.
        attributes = load_attributes(conn, [r["id"] for r in candidates])
    results, seen = [], set()
    for r in candidates:
        key = (r["company"], _base_name(r["product_name"]))
        if key in seen:
            continue
        seen.add(key)
        r["attributes"] = attributes.get(r["id"])
        r.pop("id", None)
        r.pop("distance", None)
        results.append(r)
        if len(results) >= top_k:
            break
    return results


# Needs-assessment coverage key -> extracted coverage type (product_attributes).
NEEDS_TO_COVERAGE_TYPE: dict[str, str] = {
    "accident_coverage": "accident",
    "medical_daily": "daily",
    "disability_monthly": "ltc",
    "cancer_coverage": "cancer",
    "life_coverage": "life",
}


def recommend_products_for_assessment(priority_keys: list[str], top_k: int = 3) -> list[dict]:
    """Up to top_k on-sale products, one per need in priority order.

    Picks by what the product's clauses actually cover (product_attributes
    .coverage_types), preferring main policies over riders; falls back to the
    old category match only when no extracted product covers that need.
    """
    seen: set[str] = set()
    result: list[dict] = []
    with get_inventory_connection() as conn:
        extracted = [
            (row_to_dict(r), json.loads(r["attributes"] or "{}"))
            for r in conn.execute(
                """
                SELECT p.product_id, p.product_name, p.company_name AS company, p.category, p.currency,
                       p.status, p.source_url, a.attributes
                FROM product_attributes a JOIN insurance_products p ON p.id = a.product_db_id
                WHERE p.status <> 'discontinued'
                ORDER BY p.id
                """
            ).fetchall()
        ]
        for key in priority_keys:
            if len(result) >= top_k:
                break
            coverage = NEEDS_TO_COVERAGE_TYPE.get(key)
            if not coverage or coverage in seen:
                continue
            seen.add(coverage)
            matches = [(p, a) for p, a in extracted if coverage in (a.get("coverage_types") or [])]
            matches.sort(key=lambda pa: (bool(pa[1].get("is_rider")), len(pa[1].get("coverage_types") or [])))
            if matches:
                product, attrs = matches[0]
                product.pop("attributes", None)
                product["coverage_types"] = attrs.get("coverage_types") or []
                result.append(product)
                continue
            cat = NEEDS_TO_CATEGORY.get(key)
            row = conn.execute(
                """
                SELECT p.product_id, p.product_name, p.company_name AS company, p.category, p.currency, p.status, p.source_url
                FROM insurance_products p
                WHERE p.category = ? AND p.status <> 'discontinued'
                ORDER BY CASE WHEN p.source = 'tii' THEN 1 ELSE 0 END, p.id
                LIMIT 1
                """,
                (cat,),
            ).fetchone()
            if row is not None:
                result.append(row_to_dict(row))
    return result


_STATUS_LABEL = {"active": "販售中", "discontinued": "已停售"}


_COVERAGE_LABEL = {
    "life": "壽險", "cancer": "癌症", "critical": "重大疾病/傷病", "accident": "意外",
    "daily": "住院日額", "medical": "實支實付/醫療", "ltc": "長照/失能扶助",
}


def _facts_lines(attrs: dict) -> list[str]:
    """Clause facts as short indented lines -- all of it traceable to the
    product's own clause text (values without evidence were dropped at
    extraction time)."""
    lines = []
    types = "、".join(_COVERAGE_LABEL.get(t, t) for t in attrs.get("coverage_types") or [])
    head = []
    if types:
        head.append(f"保障：{types}")
    if attrs.get("is_rider") is not None:
        head.append("附約" if attrs["is_rider"] else "主約")
    if attrs.get("issue_age"):
        age = attrs["issue_age"]
        head.append(f"投保年齡 {age.get('min', '?')}～{age.get('max', '?')} 歲")
    if attrs.get("coverage_period"):
        head.append(f"保險期間：{attrs['coverage_period']}")
    if attrs.get("payment_terms"):
        head.append("繳費年期：" + "、".join(attrs["payment_terms"][:6]))
    if head:
        lines.append("   " + "；".join(head))
    if attrs.get("waiting_periods"):
        lines.append("   等待期：" + "、".join(
            f"{w.get('target') or '一般'} {w.get('days')} 日" for w in attrs["waiting_periods"][:4]))
    if attrs.get("benefits"):
        lines.append("   給付項目：" + "、".join(b.get("name", "") for b in attrs["benefits"][:8]))
    if attrs.get("limits"):
        lines.append("   給付限制：" + "；".join(x[:80] for x in attrs["limits"][:3]))
    if attrs.get("exclusions"):
        lines.append("   除外責任（節錄）：" + "；".join(x[:40] for x in attrs["exclusions"][:6]))
    return lines


def format_context(products: list[dict]) -> str:
    if not products:
        return ""

    lines = [
        "【資料庫參考商品】以下是從商品資料庫中語意檢索到的相關保險商品"
        "（有「給付項目／除外責任」的是從該商品條款擷取的內容，可作為回答依據；"
        "沒有的只有商品名稱，不得自行推測其條款內容）：",
        "",
    ]
    for p in products:
        status = _STATUS_LABEL.get(p.get("status") or "", "")
        attrs = p.get("attributes")
        note = "" if attrs else "（僅有商品名稱，無條款資料）"
        lines.append(
            f"• {p['product_name']}｜{p['company']}｜{p['category']}｜{p.get('currency') or ''}"
            + (f"｜{status}" if status else "")
            + note
        )
        if attrs:
            lines.extend(_facts_lines(attrs))
    lines.append("")
    return "\n".join(lines)
