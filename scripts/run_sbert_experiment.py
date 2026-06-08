"""
Sentence-BERT 純向量相似度 Baseline 實驗腳本

實驗設計：
  不使用 LLM 生成。以 Sentence-BERT 對用戶查詢與 780 筆商品描述
  計算餘弦相似度，取 top-5 商品直接輸出排名清單。
  用途：作為「無 LLM 推理」的 baseline，對照 no_rag（純 LLM 記憶）
  與 pdf_rag（RAG + LLM）的品質差異。

輸出：scripts/sbert_results.json（格式與 experiment_results.json 相同，
      供 evaluate_multimodel.py 直接讀入評審）
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

PRODUCTS_PATH = Path(__file__).parent.parent / "backend" / "data" / "crawled_products_with_pdf_dm_links.json"
EXP_PATH      = Path(__file__).parent / "experiment_results.json"
OUTPUT_PATH   = Path(__file__).parent / "sbert_results.json"
MODEL_NAME    = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K         = 5
N_RUNS        = 3  # 結果確定性，3 runs 相同；保持與其他條件一致的格式

SCENARIOS = [
    {
        "scenario_id":    "S01",
        "scenario_label": "建築工人意外險",
        "message": "我是一名建築工人，工作危險性較高，每個月預算大概 500 元，想保意外傷害相關的保險，請問哪個商品適合我？",
    },
    {
        "scenario_id":    "S08",
        "scenario_label": "上班族補強醫療",
        "message": "我是 35 歲的上班族，已有基本團保，想補強住院醫療保障，預算每月 1000 元左右，有什麼建議？",
    },
    {
        "scenario_id":    "S13",
        "scenario_label": "55歲家庭主婦",
        "message": "我今年 55 歲，家庭主婦，小孩都長大了，想為自己準備一份保障兼退休規劃的保險，預算每月 3000 元，請推薦。",
    },
]


def load_products():
    data = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
    return data["products"]


def build_product_embeddings(products, model):
    texts = [
        f"{p['product_name']} {p['company']} {p['category']}"
        for p in products
    ]
    print(f"建立 {len(texts)} 筆商品向量嵌入...")
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=True)


def format_sbert_response(scenario_message: str, top_products: list[dict], scores: list[float]) -> str:
    """格式化純向量相似度排序結果，作為「回應」供 LLM-as-Judge 評審。"""
    lines = [
        f"根據您的需求，以下是向量語意相似度（Sentence-BERT）排序最相關的 {TOP_K} 筆保險商品：",
        "",
    ]
    for i, (p, s) in enumerate(zip(top_products, scores), 1):
        lines.append(f"{i}. {p['product_name']}｜{p['company']}｜{p['category']}（相似度：{s:.3f}）")

    lines += [
        "",
        "（本結果由向量語意相似度自動排序，不含 AI 顧問建議、條款說明或適配分析）",
    ]
    return "\n".join(lines)


def main():
    print(f"載入模型：{MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    products = load_products()
    product_embs = build_product_embeddings(products, model)

    results = []
    for scenario in SCENARIOS:
        print(f"\n情境：{scenario['scenario_id']} {scenario['scenario_label']}")
        query_emb = model.encode([scenario["message"]], normalize_embeddings=True)[0]
        sim_scores = product_embs @ query_emb
        top_idx = np.argsort(sim_scores)[::-1][:TOP_K]

        top_products = [products[i] for i in top_idx]
        top_scores   = [float(sim_scores[i]) for i in top_idx]
        reply        = format_sbert_response(scenario["message"], top_products, top_scores)

        # print(reply)  # skip — cp950 console can't render CJK from SBERT output

        # 3 runs 內容相同（確定性），但保持格式一致
        for run in range(1, N_RUNS + 1):
            results.append({
                "scenario_id":    scenario["scenario_id"],
                "scenario_label": scenario["scenario_label"],
                "mode":           "sbert_only",
                "run":            run,
                "message":        scenario["message"],
                "reply":          reply,
                "top_products":   [
                    {"product_name": p["product_name"], "company": p["company"],
                     "category": p["category"], "similarity": s}
                    for p, s in zip(top_products, top_scores)
                ],
            })

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！共 {len(results)} 筆，結果存至 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
