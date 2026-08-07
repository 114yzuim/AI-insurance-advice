"""
Full PDF RAG Service — Docling 版
讀取 12 筆保險商品 PDF 條款 → Docling 解析結構 → 按標題/條文切段 → 向量索引
提供 retrieve_clause_chunks() 給 chat router 使用
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from docling.document_converter import DocumentConverter
from sentence_transformers import SentenceTransformer

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_PRODUCTS_JSON = _ROOT / "data" / "selected_products.json"

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 80

# ── 全域快取 ──────────────────────────────────────────────────────────────────
_converter: DocumentConverter | None = None
_model: SentenceTransformer | None = None
_chunk_embeddings: np.ndarray | None = None
_chunks: list[dict] | None = None


# ── Docling 解析 ──────────────────────────────────────────────────────────────

def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


def _extract_markdown(pdf_path: Path) -> str:
    """用 Docling 把 PDF 解析成保留結構的 Markdown。"""
    result = _get_converter().convert(str(pdf_path))
    return result.document.export_to_markdown()


# ── 切段策略 ──────────────────────────────────────────────────────────────────

def _split_into_chunks(markdown: str) -> list[str]:
    """
    Docling 輸出的 Markdown 已帶有標題層級（# / ## / ###）和表格。
    切段策略：
    1. 以 Markdown 標題（#）為主要分隔點，每個標題段落為一個 chunk
    2. 超過 _CHUNK_SIZE 的段落再以句號/分號切細（帶 overlap）
    3. 保留表格結構（不在表格中間切斷）
    """
    # 以標題行分段（保留標題本身在 chunk 開頭）
    sections = re.split(r'\n(?=#{1,4} )', markdown)
    sections = [s.strip() for s in sections if s.strip() and len(s.strip()) > 20]

    raw_chunks: list[str] = []
    for section in sections:
        if len(section) <= _CHUNK_SIZE:
            raw_chunks.append(section)
        else:
            # 超長段落：先保留標題行，剩餘部分以句號/分號切細
            lines = section.split('\n')
            header = lines[0] if lines[0].startswith('#') else ""
            body = '\n'.join(lines[1:] if header else lines)

            sentences = re.split(r'(?<=[。；！？\n])', body)
            current = header + "\n" if header else ""
            for sent in sentences:
                if len(current) + len(sent) <= _CHUNK_SIZE:
                    current += sent
                else:
                    if current.strip():
                        raw_chunks.append(current.strip())
                    # overlap：新 chunk 從標題 + 上一句開頭
                    tail = current[-_CHUNK_OVERLAP:] if len(current) > _CHUNK_OVERLAP else current
                    current = (header + "\n" if header else "") + tail + sent
            if current.strip():
                raw_chunks.append(current.strip())

    return [c for c in raw_chunks if len(c) > 30]


# ── 索引建立 ──────────────────────────────────────────────────────────────────

def _build_chunks() -> list[dict]:
    with open(_PRODUCTS_JSON, encoding="utf-8") as f:
        products = json.load(f)["products"]

    all_chunks: list[dict] = []
    for prod in products:
        pdf_path = _ROOT.parent / prod["pdf_path"]
        if not pdf_path.exists():
            pdf_path = _ROOT / Path(prod["pdf_path"]).name
        if not pdf_path.exists():
            print(f"[pdf_rag] 找不到 PDF：{prod['pdf_path']}")
            continue

        print(f"[pdf_rag] Docling 解析：{prod['product_name']}")
        try:
            markdown = _extract_markdown(pdf_path)
        except Exception as e:
            print(f"[pdf_rag] 解析失敗 {prod['product_name']}：{e}")
            continue

        chunks_text = _split_into_chunks(markdown)
        for idx, text in enumerate(chunks_text):
            all_chunks.append({
                "chunk_id": f"{prod['id']}_{idx:03d}",
                "product_id": prod["id"],
                "product_name": prod["product_name"],
                "company": prod["company"],
                "category": prod["category"],
                "text": text,
            })

    return all_chunks


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_index() -> tuple[np.ndarray, list[dict]]:
    global _chunk_embeddings, _chunks
    if _chunk_embeddings is None:
        print("[pdf_rag] 建立 Docling PDF RAG 索引，首次需要約 1-2 分鐘...")
        _chunks = _build_chunks()
        model = _get_model()
        texts = [c["text"] for c in _chunks]
        _chunk_embeddings = model.encode(
            texts, normalize_embeddings=True, show_progress_bar=True, batch_size=64
        )
        print(f"[pdf_rag] 索引完成：{len(_chunks)} chunks from {len(set(c['product_id'] for c in _chunks))} PDFs")
    return _chunk_embeddings, _chunks  # type: ignore[return-value]


# ── 公開 API ──────────────────────────────────────────────────────────────────

def retrieve_clause_chunks(query: str, top_k: int = 6) -> list[dict]:
    """回傳與查詢最相關的 top_k 條款段落（含商品 metadata）。"""
    embeddings, chunks = _get_index()
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0]
    scores: np.ndarray = embeddings @ query_vec
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [chunks[int(i)] for i in top_indices]


_product_meta_embeddings: np.ndarray | None = None
_product_meta_list: list[dict] | None = None


def _get_product_meta_index() -> tuple[np.ndarray, list[dict]]:
    """對 12 份已索引商品的 (名稱+公司+類別) 建立獨立的商品層級嵌入，
    避免條款全文 chunk 層級的詞彙噪音干擾商品選定（chunk 內大量保單樣板文字
    會讓語意嵌入在商品間混淆，而簡短的商品 metadata 描述判別力更穩定）。"""
    global _product_meta_embeddings, _product_meta_list
    if _product_meta_embeddings is None:
        with open(_PRODUCTS_JSON, encoding="utf-8") as f:
            products = json.load(f)["products"]
        model = _get_model()
        texts = [f"{p['product_name']}，{p['company']}，{p['category']}" for p in products]
        _product_meta_embeddings = model.encode(texts, normalize_embeddings=True)
        _product_meta_list = products
    return _product_meta_embeddings, _product_meta_list  # type: ignore[return-value]


def retrieve_full_product_text(query: str) -> dict | None:
    """回傳與查詢最相關之單一商品的「全文」（該商品所有 chunk 依原順序重組），
    供「全文 vs 切割文」消融實驗的全文條件使用。

    商品選定改用商品 metadata（名稱+公司+類別）的獨立嵌入比對，而非條款全文
    chunk 層級的相似度——後者在 12 份商品的條款全文中含大量共通保單樣板語言，
    chunk 層級比對曾在測試中誤選類別不符的商品（如將意外傷害需求誤導向還本養老商品）。
    """
    meta_embeddings, products = _get_product_meta_index()
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0]
    scores: np.ndarray = meta_embeddings @ query_vec
    best_idx = int(np.argmax(scores))
    best_product_id = products[best_idx]["id"]

    _, chunks = _get_index()
    product_chunks = sorted(
        (c for c in chunks if c["product_id"] == best_product_id),
        key=lambda c: c["chunk_id"],
    )
    full_text = "\n\n".join(c["text"] for c in product_chunks)
    return {
        "product_id": best_product_id,
        "product_name": product_chunks[0]["product_name"],
        "company": product_chunks[0]["company"],
        "category": product_chunks[0]["category"],
        "full_text": full_text,
    }


def retrieve_single_product_chunks(query: str, top_k: int = 6) -> list[dict]:
    """選定單一最佳商品（與 retrieve_full_product_text 相同的商品選定邏輯），
    但只回傳該商品內與查詢最相關的 top_k 條款 chunks（而非全文重組）。

    用於消融實驗，隔離兩個原本混淆在一起的變因：
      - 對照 full_text：候選商品數同為 1，唯一差異為「全文 vs 切割」
      - 對照 docling_chunk：切割方式相同，唯一差異為「候選商品數（1 vs 多商品）」
    """
    meta_embeddings, products = _get_product_meta_index()
    model = _get_model()
    query_vec = model.encode([query], normalize_embeddings=True)[0]
    meta_scores: np.ndarray = meta_embeddings @ query_vec
    best_idx = int(np.argmax(meta_scores))
    best_product_id = products[best_idx]["id"]

    embeddings, chunks = _get_index()
    member_idxs = [i for i, c in enumerate(chunks) if c["product_id"] == best_product_id]
    if not member_idxs:
        return []
    sub_scores: np.ndarray = embeddings[member_idxs] @ query_vec
    order = np.argsort(sub_scores)[::-1][:top_k]
    return [chunks[member_idxs[int(j)]] for j in order]


def format_full_text_context(product: dict | None) -> str:
    if not product:
        return ""
    return (
        f"【保單條款全文參考資料】以下為「{product['product_name']}"
        f"（{product['company']}｜{product['category']}）」之完整條款全文，"
        f"請依據以下全文內容進行推薦，並引用具體條款說明：\n\n{product['full_text']}"
    )


def format_clause_context(chunks: list[dict]) -> str:
    """將檢索到的條款 chunks 格式化成 Claude 可用的 context string。"""
    if not chunks:
        return ""

    lines = [
        "【保單條款參考資料】以下摘自相關保險商品的條款原文，請依據這些條款內容進行推薦，並引用具體條款說明：",
        "",
    ]
    current_product = None
    for c in chunks:
        if c["product_name"] != current_product:
            current_product = c["product_name"]
            lines.append(f"▌{c['product_name']}（{c['company']}｜{c['category']}）")
        lines.append(c["text"])
        lines.append("")

    return "\n".join(lines)
