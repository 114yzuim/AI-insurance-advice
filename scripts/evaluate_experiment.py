"""
GPT-4o（或 Claude）評分腳本
讀取 experiment_results.json，對每筆回應用 LLM-as-Judge 評 D1/D2/D3

評分維度（同論文附錄 A rubric）：
  D1 需求覆蓋率  1=未覆蓋核心需求  2=部分覆蓋  3=完整覆蓋
  D2 條款一致性  1=無具體條款依據  2=有產品引用但欠缺條款細節  3=引用具體條款原文
  D3 資訊完整性  1=資訊嚴重缺失  2=基本完整但有缺項  3=完整含除外/注意事項

AHP 權重（論文 Table 2a）：
  D1 = 0.648, D2 = 0.230, D3 = 0.122

執行：python scripts/evaluate_experiment.py
"""

import json
import os
import time
from pathlib import Path
from anthropic import Anthropic

RESULTS_PATH = Path(__file__).parent / "experiment_results.json"
AHP_WEIGHTS = {"D1": 0.648, "D2": 0.230, "D3": 0.122}

client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY") or
    open(Path(__file__).parent.parent / "backend" / ".env").read().split("=", 1)[1].strip())

EVAL_SYSTEM = """你是一位嚴格、中立的保險推薦品質評審員。
你的任務是依照評分 rubric，對 AI 保險顧問的回應進行評分。
請嚴格按照 rubric 標準，不要給分太慷慨，每個維度只能給 1、2、3 分。
以 JSON 格式回覆，不要有其他文字。"""

EVAL_PROMPT_TEMPLATE = """【用戶情境】
{scenario_label}

【用戶問題】
{message}

【AI 回應】
{reply}

【評分 Rubric】

D1 需求覆蓋率（這份回應是否解答了用戶的核心保險需求？）
  1 = 未能覆蓋用戶的核心需求（沒有推薦任何產品或方向）
  2 = 部分覆蓋（有推薦但不完整，例如只給方向、沒有具體產品）
  3 = 完整覆蓋（針對用戶需求提供了具體且可行的推薦）

D2 條款一致性（回應是否引用了真實的保單條款或產品具體資訊？）
  1 = 無任何條款或商品具體資訊（純靠 LLM 通識知識）
  2 = 有提到商品名稱或公司，但欠缺條款細節（如除外責任、保費數字、承保年齡等）
  3 = 明確引用了條款原文或具體保費數字、承保條件等可核實的資訊

D3 資訊完整性（回應是否包含用戶做決策所需的完整資訊？）
  1 = 嚴重缺失（缺少對用戶特定情況的考量，例如職業限制、預算對應）
  2 = 基本完整，但有 1～2 個明顯缺項（如未提及除外責任，或未確認預算可行性）
  3 = 完整（包含除外責任提醒、預算可行性分析、投保注意事項等）

請以以下 JSON 格式回覆（數字只能是 1、2、3）：
{{"D1": <分數>, "D2": <分數>, "D3": <分數>, "notes": "<簡短說明判分依據，50字內>"}}"""


def evaluate_one(item: dict) -> dict:
    prompt = EVAL_PROMPT_TEMPLATE.format(
        scenario_label=item["scenario_label"],
        message=item["message"],
        reply=item["reply"],
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=EVAL_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    try:
        scores = json.loads(raw)
        d1, d2, d3 = int(scores["D1"]), int(scores["D2"]), int(scores["D3"])
        w_score = round(d1 * AHP_WEIGHTS["D1"] + d2 * AHP_WEIGHTS["D2"] + d3 * AHP_WEIGHTS["D3"], 3)
        return {"D1": d1, "D2": d2, "D3": d3, "W_score": w_score, "evaluator_notes": scores.get("notes", "")}
    except Exception as e:
        return {"D1": None, "D2": None, "D3": None, "W_score": None, "evaluator_notes": f"parse error: {raw}"}


def main():
    with open(RESULTS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    for i, item in enumerate(data):
        if item["D1"] is not None:
            print(f"[{i+1}/{total}] {item['scenario_id']} {item['mode']} run{item['run']} — 已有評分，略過")
            continue

        print(f"[{i+1}/{total}] 評分中：{item['scenario_id']} | {item['mode']} | run {item['run']}")
        scores = evaluate_one(item)
        item.update(scores)
        print(f"  D1={scores['D1']} D2={scores['D2']} D3={scores['D3']} W={scores['W_score']}  {scores['evaluator_notes']}")
        time.sleep(0.8)

    RESULTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n評分完成，結果已存至 {RESULTS_PATH}")

    # 輸出彙整表
    print("\n=== 各條件平均分 ===")
    from collections import defaultdict
    sums = defaultdict(lambda: {"D1": 0, "D2": 0, "D3": 0, "W": 0, "n": 0})
    for item in data:
        if item["D1"] is None:
            continue
        key = f"{item['scenario_id']}|{item['mode']}"
        sums[key]["D1"] += item["D1"]
        sums[key]["D2"] += item["D2"]
        sums[key]["D3"] += item["D3"]
        sums[key]["W"] += item["W_score"]
        sums[key]["n"] += 1

    print(f"{'情境|條件':<25} {'D1':>4} {'D2':>4} {'D3':>4} {'W-Score':>8}")
    print("-" * 50)
    for key in sorted(sums.keys()):
        v = sums[key]
        n = v["n"]
        print(f"{key:<25} {v['D1']/n:>4.2f} {v['D2']/n:>4.2f} {v['D3']/n:>4.2f} {v['W']/n:>8.3f}")


if __name__ == "__main__":
    main()
