"""
重跑 matrix_results.json 中 LLM3_Gemini 的 27 筆（原版因 thinking_budget 未關閉，
981/1024 token 被內部思考消耗，導致回應被截斷至 50-60 字元，不可用）。
修正後的 generate_gemini()（thinking_budget=0）重新生成，原地覆寫 matrix_results.json
裡對應的列。

執行：python scripts/rerun_gemini_matrix.py
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

from multivendor_generate import generate_gemini

RESULTS_PATH = Path(__file__).parent / "matrix_results.json"

SCENARIOS = {
    "S01": "我是一名建築工人，工作危險性較高，每個月預算大概 500 元，想保意外傷害相關的保險，請問哪個商品適合我？",
    "S08": "我是 35 歲的上班族，已有基本團保，想補強住院醫療保障，預算每月 1000 元左右，有什麼建議？",
    "S13": "我今年 55 歲，家庭主婦，小孩都長大了，想為自己準備一份保障兼退休規劃的保險，預算每月 3000 元，請推薦。",
}


def build_context(strategy: str, message: str) -> str:
    if strategy == "full_text":
        product = retrieve_full_product_text(message)
        return format_full_text_context(product)
    elif strategy == "docling_chunk":
        chunks = retrieve_clause_chunks(message, top_k=6)
        return format_clause_context(chunks)
    elif strategy == "chunk_profile":
        profile = asyncio.run(extract_profile([], message))
        aug_query = build_augmented_query(message, profile)
        chunks = retrieve_clause_chunks(aug_query, top_k=6)
        return format_clause_context(chunks)
    raise ValueError(strategy)


def main():
    data = json.load(open(RESULTS_PATH, encoding="utf-8"))
    targets = [d for d in data if d["generator"] == "LLM3_Gemini"]
    print(f"重跑 {len(targets)} 筆 Gemini 回應...")

    # cache context per (scenario, strategy) to avoid rebuilding repeatedly
    ctx_cache = {}
    done = 0
    for item in targets:
        key = (item["scenario_id"], item["strategy"])
        if key not in ctx_cache:
            ctx_cache[key] = build_context(item["strategy"], SCENARIOS[item["scenario_id"]])
        context = ctx_cache[key]

        done += 1
        print(f"[{done}/{len(targets)}] {item['scenario_id']} | {item['strategy']} | run {item['run']}")
        try:
            reply = generate_gemini(item["message"], context)
        except Exception as e:
            reply = f"[ERROR] {e}"
        item["reply"] = reply
        item["timestamp"] = datetime.now().isoformat()
        time.sleep(0.5)

    RESULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！已覆寫 {RESULTS_PATH}")


if __name__ == "__main__":
    main()
