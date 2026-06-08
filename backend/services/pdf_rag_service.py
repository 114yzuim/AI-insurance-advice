"""
Full PDF RAG Service
讀取 12 筆保險商品 PDF 條款 → 切割段落 → 向量索引
提供 retrieve_clause_chunks() 給 chat router 使用
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pdfplumber
from sentence_transformers import SentenceTransformer

# ── 路徑設定 ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
_PRODUCTS_JSON = _ROOT / "data" / "selected_products.json"
_PDF_DIR = _ROOT / "data" / "pdfs"

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_CHUNK_SIZE = 500      # 每個 chunk 最大字元數
_CHUNK_OVERLAP = 80    # chunk 間重疊字元數，保留上下文

# ── 全域快取（首次查詢時建立，後續重用）─────────────────────────────────────
_model: SentenceTransformer | None = None
_chunk_embeddings: np.ndarray | None = None
_chunks: list[dict] | None = None   # [{text, product_id, product_name, company, category}, ...]


# ── 文字切割 ──────────────────────────────────────────────────────────────────

def _extract_pages(pdf_path: Path) -> list[str]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t and t.strip():
                pages.append(t.strip())
    return pages


def _split_into_chunks(full_text: str) -> list[str]:
    """
    分段策略：
    1. 先以空行（段落）切分
    2. 超過 _CHUNK_SIZE 的段落再以句號/分號切細
    3. 最後做滑動視窗合併（帶 overlap）
    """
    # 以雙換行或條款序號（第X條）作為自然分隔
    paragraphs = re.split(r"\n{2,}|(?=第[一二三四五六七八九十百\d]+條)", full_text)
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 30]

    raw_chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= _CHUNK_SIZE:
            raw_chunks.append(para)
        else:
            # 超長段落：以句號/分號切細
            sentences = re.split(r"(?<=[。；！？])", para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) <= _CHUNK_SIZE:
                    current += sent
                else:
                    if current:
                        raw_chunks.append(current.strip())
                    current = sent
            if current.strip():
                raw_chunks.append(current.strip())

    # 滑動視窗合併（帶 overlap）
    if not raw_chunks:
        return []

    merged: list[str] = []
    i = 0
    while i < len(raw_chunks):
        chunk = raw_chunks[i]
        # 往後追加直到超過 _CHUNK_SIZE
        j = i + 1
        while j < len(raw_chunks) and len(chunk) + len(raw_chunks[j]) < _CHUNK_SIZE:
            chunk += "\n" + raw_chunks[j]
            j += 1
        merged.append(chunk.strip())
        # overlap：回退一個 chunk 開始下一組
        i = j - 1 if j > i + 1 else j

    return merged


def _build_chunks() -> list[dict]:
    with open(_PRODUCTS_JSON, encoding="utf-8") as f:
        products = json.load(f)["products"]

    all_chunks: list[dict] = []
    for prod in products:
        pdf_path = _ROOT.parent / prod["pdf_path"]   # relative to project root
        if not pdf_path.exists():
            # fallback: try relative to _ROOT
            pdf_path = _ROOT / Path(prod["pdf_path"]).name if not pdf_path.exists() else pdf_path
        if not pdf_path.exists():
            print(f"[pdf_rag] 找不到 PDF：{prod['pdf_path']}")
            continue

        pages = _extract_pages(pdf_path)
        full_text = "\n\n".join(pages)
        chunks_text = _split_into_chunks(full_text)

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


# ── 索引建立 ──────────────────────────────────────────────────────────────────

def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _get_index() -> tuple[np.ndarray, list[dict]]:
    global _chunk_embeddings, _chunks
    if _chunk_embeddings is None:
        print("[pdf_rag] 建立 Full PDF RAG 索引，首次需要約 30 秒...")
        _chunks = _build_chunks()
        model = _get_model()
        texts = [c["text"] for c in _chunks]
        _chunk_embeddings = model.encode(
            texts, normalize_embeddings=True, show_progress_bar=True, batch_size=64
        )
        print(f"[pdf_rag] 索引完成：{len(_chunks)} chunks from 12 PDFs")
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
