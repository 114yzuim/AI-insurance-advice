"""
metadata_rag 中間條件實驗腳本（回應審查 P0：補齊 no_rag → metadata_rag → pdf_rag 三階消融）

設計動機：原評估僅有 no_rag（無商品資料）與 pdf_rag（條款全文），
無法將 D2 提升歸因於「條款 grounding」還是「有任何商品資料」。
本腳本補上中間條件 metadata_rag：僅注入商品 metadata（名稱/公司/類別），
不含 PDF 條款、不含 Profile-Augmented 個人化，與其他兩條件共用相同的單一查詢字串，
確保三條件唯一差異為「注入的知識層級」。

實作說明：生產環境的 metadata_rag 端點在偵測到年齡/預算時會觸發 Profile-Augmented
檢索（含條款補充），會污染本條件。故本腳本直接呼叫底層服務（retrieve_relevant_products
+ format_context + get_advisory_response），繞過 profile 與條款補充，取得乾淨的
「純 metadata grounding」生成結果。

輸出：scripts/metadata_results.json（格式與 experiment_results.json 一致）
執行前請確認 backend/.env 內 CLAUDE_API_KEY 有效且額度充足。
執行：python scripts/run_metadata_experiment.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# 載入 backend 模組
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

from services.rag_service import retrieve_relevant_products, format_context
from services.claude_service import get_advisory_response

OUTPUT_PATH = Path(__file__).parent / "metadata_results.json"

# 與 run_experiment.py / run_sbert_experiment.py 完全相同的 3 情境查詢
SCENARIOS = [
    {
        "scenario_id": "S01",
        "scenario_label": "建築工人意外險",
        "message": "我是一名建築工人，工作危險性較高，每個月預算大概 500 元，想保意外傷害相關的保險，請問哪個商品適合我？",
    },
    {
        "scenario_id": "S08",
        "scenario_label": "上班族補強醫療",
        "message": "我是 35 歲的上班族，已有基本團保，想補強住院醫療保障，預算每月 1000 元左右，有什麼建議？",
    },
    {
        "scenario_id": "S13",
        "scenario_label": "55歲家庭主婦",
        "message": "我今年 55 歲，家庭主婦，小孩都長大了，想為自己準備一份保障兼退休規劃的保險，預算每月 3000 元，請推薦。",
    },
]
RUNS_PER_SCENARIO = 3


async def main():
    results = []
    total = len(SCENARIOS) * RUNS_PER_SCENARIO
    done = 0
    for scenario in SCENARIOS:
        # metadata-only context：top-5 商品名稱/公司/類別，無條款、無 profile
        products = retrieve_relevant_products(scenario["message"], top_k=5)
        context = format_context(products)
        for run_idx in range(1, RUNS_PER_SCENARIO + 1):
            done += 1
            print(f"[{done}/{total}] {scenario['scenario_id']} | metadata_rag | run {run_idx}")
            reply = await get_advisory_response(scenario["message"], [], context)
            results.append({
                "scenario_id": scenario["scenario_id"],
                "scenario_label": scenario["scenario_label"],
                "mode": "metadata_rag",
                "run": run_idx,
                "message": scenario["message"],
                "reply": reply,
                "retrieved_products": [
                    {"product_name": p["product_name"], "company": p["company"], "category": p["category"]}
                    for p in products
                ],
                "timestamp": datetime.now().isoformat(),
            })

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！共 {len(results)} 筆，存至 {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
