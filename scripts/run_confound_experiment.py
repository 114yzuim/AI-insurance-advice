"""
混淆變因隔離實驗（回應指導教授：full_text 同時改變了「文件處理粒度」與「檢索候選商品數」）。

新增對照條件 single_product_chunk：
  與 full_text 相同的「單一最佳商品」選定邏輯，但只給該商品內 top-6 條款 chunks（非全文重組）。

藉此把原本混在一起的兩個變因拆開：
  full_text          = 單一商品 + 全文
  single_product_chunk = 單一商品 + 切割        ← 本實驗新增
  docling_chunk      = 多商品候選 + 切割

  full_text  vs single_product_chunk → 純粹「全文 vs 切割」（商品數固定為 1）
  single_product_chunk vs docling_chunk → 純粹「檢索廣度 1 vs 多」（切割方式相同）

3 生成器（Claude/GPT-4o/Gemini）× 3 情境 × 3 runs = 27 筆，schema 與 matrix_results.json 一致，
可直接餵給 evaluate_matrix.py 評分。

輸出：scripts/confound_results.json
執行：python scripts/run_confound_experiment.py
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
    retrieve_single_product_chunks, format_clause_context,
)
from multivendor_generate import generate_claude, generate_gpt4o, generate_gemini

OUTPUT_PATH = Path(__file__).parent / "confound_results.json"

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

STRATEGY = "single_product_chunk"
RUNS_PER_SCENARIO = 3


def main():
    results = []
    total = len(GENERATORS) * len(SCENARIOS) * RUNS_PER_SCENARIO
    done = 0

    for gen_name, gen_fn in GENERATORS.items():
        for scenario in SCENARIOS:
            chunks = retrieve_single_product_chunks(scenario["message"], top_k=6)
            context = format_clause_context(chunks)
            for run_idx in range(1, RUNS_PER_SCENARIO + 1):
                done += 1
                print(f"[{done}/{total}] {scenario['scenario_id']} | {gen_name} | {STRATEGY} | run {run_idx}")
                try:
                    reply = gen_fn(scenario["message"], context)
                except Exception as e:
                    reply = f"[ERROR] {e}"
                results.append({
                    "scenario_id": scenario["scenario_id"],
                    "scenario_label": scenario["scenario_label"],
                    "generator": gen_name,
                    "strategy": STRATEGY,
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
