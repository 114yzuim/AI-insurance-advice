"""
教授原始表格的完整消融實驗：
  列（生成引擎）：LLM1=Claude／LLM2=GPT-4o／LLM3=Gemini（＋SBERT 另行處理，見 aggregate）
  欄（文件處理策略）：
    full_text      = 全文（單一最相關商品之 Docling 全文重組，不切割）
    chunk_profile  = 切割段落 + human profile（Docling top-6 chunks，查詢已注入 profile）
    docling_chunk  = Docling 切割，無 profile（= 現有 pdf_rag 條件之檢索方式）

新增 8 個格子（LLM1×full_text、LLM1×chunk_profile、LLM2×全部3欄、LLM3×全部3欄）；
LLM1×docling_chunk 已有資料（experiment_results.json 的 pdf_rag），不重跑。

輸出：scripts/matrix_results.json
執行：python scripts/run_matrix_experiment.py
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(ROOT / "backend" / ".env")

from services.pdf_rag_service import (
    retrieve_clause_chunks, format_clause_context,
    retrieve_full_product_text, format_full_text_context,
)
from services.profile_rag_service import extract_profile, build_augmented_query
import asyncio

from multivendor_generate import generate_claude, generate_gpt4o, generate_gemini

OUTPUT_PATH = Path(__file__).parent / "matrix_results.json"

SCENARIOS = [
    {
        "scenario_id": "S01", "scenario_label": "建築工人意外險",
        "message": "我是一名建築工人，工作危險性較高，每個月預算大概 500 元，想保意外傷害相關的保險，請問哪個商品適合我？",
    },
    {
        "scenario_id": "S08", "scenario_label": "上班族補強醫療",
        "message": "我是 35 歲的上班族，已有基本團保，想補強住院醫療保障，預算每月 1000 元左右，有什麼建議？",
    },
    {
        "scenario_id": "S13", "scenario_label": "55歲家庭主婦",
        "message": "我今年 55 歲，家庭主婦，小孩都長大了，想為自己準備一份保障兼退休規劃的保險，預算每月 3000 元，請推薦。",
    },
]

GENERATORS = {
    "LLM1_Claude": generate_claude,
    "LLM2_GPT4o": generate_gpt4o,
    "LLM3_Gemini": generate_gemini,
}

# (generator, strategy) cells to run. LLM1 x docling_chunk skipped — reuse existing pdf_rag data.
CELLS = [
    (gen, strat)
    for gen in GENERATORS
    for strat in ["full_text", "chunk_profile", "docling_chunk"]
    if not (gen == "LLM1_Claude" and strat == "docling_chunk")
]

RUNS_PER_SCENARIO = 3


def build_context(strategy: str, message: str, history: list[dict]) -> str:
    if strategy == "full_text":
        product = retrieve_full_product_text(message)
        return format_full_text_context(product)
    elif strategy == "docling_chunk":
        chunks = retrieve_clause_chunks(message, top_k=6)
        return format_clause_context(chunks)
    elif strategy == "chunk_profile":
        profile = asyncio.run(extract_profile(history, message))
        aug_query = build_augmented_query(message, profile)
        chunks = retrieve_clause_chunks(aug_query, top_k=6)
        return format_clause_context(chunks)
    raise ValueError(strategy)


def main():
    results = []
    total = len(CELLS) * len(SCENARIOS) * RUNS_PER_SCENARIO
    done = 0

    for gen_name, strategy in CELLS:
        gen_fn = GENERATORS[gen_name]
        for scenario in SCENARIOS:
            context = build_context(strategy, scenario["message"], [])
            for run_idx in range(1, RUNS_PER_SCENARIO + 1):
                done += 1
                print(f"[{done}/{total}] {scenario['scenario_id']} | {gen_name} | {strategy} | run {run_idx}")
                try:
                    reply = gen_fn(scenario["message"], context)
                except Exception as e:
                    reply = f"[ERROR] {e}"
                results.append({
                    "scenario_id": scenario["scenario_id"],
                    "scenario_label": scenario["scenario_label"],
                    "generator": gen_name,
                    "strategy": strategy,
                    "run": run_idx,
                    "message": scenario["message"],
                    "reply": reply,
                    "timestamp": datetime.now().isoformat(),
                })
                time.sleep(0.5)

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！共 {len(results)} 筆，存至 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
