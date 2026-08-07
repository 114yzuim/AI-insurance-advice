"""Profile-Augmented RAG 服務。

流程：
1. extract_profile()  — 用 Haiku 從對話提取 user profile（age、預算等）
2. build_augmented_query() — 把 profile 欄位拼入 query，向量搜尋更精準
3. retrieve_with_profile() — metadata 搜尋 + 自動補充 PDF 條款 chunks
"""
from __future__ import annotations

import json
import os
import pathlib

from anthropic import AsyncAnthropic

from services.pdf_rag_service import format_clause_context, retrieve_clause_chunks
from services.rag_service import format_context, retrieve_relevant_products

_client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))

_SELECTED_PRODUCTS_PATH = (
    pathlib.Path(__file__).parent.parent / "data" / "selected_products.json"
)


def _load_pdf_product_names() -> set[str]:
    try:
        products = json.loads(_SELECTED_PRODUCTS_PATH.read_text(encoding="utf-8"))
        return {p["product_name"] for p in products}
    except Exception:
        return set()


_PDF_PRODUCT_NAMES: set[str] = _load_pdf_product_names()

_EXTRACT_SYSTEM = """從對話中提取使用者提到的保險相關背景，回傳 JSON 物件。
未提及的欄位設為 null。只回傳 JSON，不要有其他文字。

欄位：
- age: 年齡（整數）
- budget_monthly: 每月保費預算（整數，元）
- has_dependents: 是否有扶養家人（布林值）
- health_status: "良好" | "有慢性病" | "有重大病史" | null
- job_risk: "一般" | "高風險" | null
- existing_coverage: 已有的保險種類（字串陣列，無則 []）

範例：{"age": 35, "budget_monthly": 2000, "has_dependents": true, "health_status": "良好", "job_risk": "一般", "existing_coverage": []}"""


async def extract_profile(history: list[dict], message: str) -> dict:
    """用 Claude Haiku 從最近對話 + 當前訊息提取 user profile。
    任何解析失敗都回傳 {} 讓呼叫端跌回標準 RAG。
    """
    recent = history[-6:] if len(history) > 6 else history
    conversation = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    conversation += f"\nuser: {message}"

    try:
        resp = await _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            temperature=0,
            system=_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": conversation}],
        )
        raw = resp.content[0].text.strip()
        # 去掉可能的 code fence
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return {}


def build_augmented_query(query: str, profile: dict) -> str:
    """把 profile 非空欄位前置到 query，使向量搜尋往符合使用者條件的商品靠近。"""
    parts: list[str] = []
    if profile.get("age"):
        parts.append(f"年齡{profile['age']}歲")
    if profile.get("has_dependents"):
        parts.append("有扶養人口")
    if profile.get("budget_monthly"):
        parts.append(f"月預算{profile['budget_monthly']}元")
    if profile.get("health_status"):
        parts.append(str(profile["health_status"]))
    if profile.get("job_risk"):
        parts.append(f"工作性質{profile['job_risk']}")
    existing: list = profile.get("existing_coverage") or []
    if existing:
        parts.append(f"已有{'、'.join(existing)}")

    return ("、".join(parts) + "，" + query) if parts else query


def retrieve_with_profile(query: str, profile: dict, top_k: int = 5) -> str:
    """
    Profile-augmented retrieval：
    1. 建構含 profile 的 augmented query
    2. Metadata 向量搜尋（780 筆）取前 top_k
    3. 若 top results 有本機 PDF 商品 → 補充 PDF 條款 chunks
    4. 回傳組合後的 context 字串
    """
    aug_query = build_augmented_query(query, profile)
    products = retrieve_relevant_products(aug_query, top_k=top_k)

    context_parts: list[str] = []

    metadata_ctx = format_context(products)
    if metadata_ctx:
        context_parts.append(metadata_ctx)

    # 若 top results 有已建立 PDF index 的商品，補充條款摘要
    has_pdf = any(p.get("product_name", "") in _PDF_PRODUCT_NAMES for p in products)
    if has_pdf:
        chunks = retrieve_clause_chunks(aug_query, top_k=3)
        clause_ctx = format_clause_context(chunks)
        if clause_ctx:
            context_parts.append(clause_ctx)

    return "\n\n".join(context_parts)
