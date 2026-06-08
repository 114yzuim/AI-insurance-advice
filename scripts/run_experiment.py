"""
Full PDF RAG 實驗腳本
比較兩個條件：
  - no_rag    : 純 LLM（無資料庫）
  - pdf_rag   : Full PDF RAG（12 份條款全文向量索引）

對 3 個測試情境各跑 3 次，結果存至 scripts/experiment_results.json

使用前請先啟動後端：
  cd backend && uvicorn main:app --reload

執行：python scripts/run_experiment.py
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime

API_BASE = "http://localhost:8000/chat"
RESULTS_PATH = Path(__file__).parent / "experiment_results.json"

# ── 3 個測試情境（沿用論文 S01/S08/S13）─────────────────────────────────────
SCENARIOS = [
    {
        "id": "S01",
        "label": "建築工人意外險",
        "message": "我是一名建築工人，工作危險性較高，每個月預算大概 500 元，想保意外傷害相關的保險，請問哪個商品適合我？",
    },
    {
        "id": "S08",
        "label": "上班族補強醫療",
        "message": "我是 35 歲的上班族，已有基本團保，想補強住院醫療保障，預算每月 1000 元左右，有什麼建議？",
    },
    {
        "id": "S13",
        "label": "55歲家庭主婦",
        "message": "我今年 55 歲，家庭主婦，小孩都長大了，想為自己準備一份保障兼退休規劃的保險，預算每月 3000 元，請推薦。",
    },
]

MODES = ["no_rag", "pdf_rag"]
RUNS_PER_SCENARIO = 3


def call_chat(message: str, mode: str) -> str:
    payload = {"message": message, "history": [], "mode": mode}
    try:
        r = requests.post(API_BASE, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["reply"]
    except Exception as e:
        return f"[ERROR] {e}"


def main():
    results = []
    total = len(SCENARIOS) * len(MODES) * RUNS_PER_SCENARIO
    done = 0

    for scenario in SCENARIOS:
        for mode in MODES:
            for run_idx in range(1, RUNS_PER_SCENARIO + 1):
                done += 1
                print(f"[{done}/{total}] {scenario['id']} | {mode} | run {run_idx}")
                reply = call_chat(scenario["message"], mode)
                results.append({
                    "scenario_id": scenario["id"],
                    "scenario_label": scenario["label"],
                    "mode": mode,
                    "run": run_idx,
                    "message": scenario["message"],
                    "reply": reply,
                    "timestamp": datetime.now().isoformat(),
                    # GPT-4o 評分欄位（後續填入）
                    "D1": None,
                    "D2": None,
                    "D3": None,
                    "W_score": None,
                    "evaluator_notes": "",
                })
                time.sleep(1.5)  # 避免 API rate limit

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！共 {len(results)} 筆回應，儲存至 {RESULTS_PATH}")


if __name__ == "__main__":
    main()
