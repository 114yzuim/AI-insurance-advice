"""
三模型交叉評審腳本
對 experiment_results.json 的 18 筆回應，分別用：
  - Claude claude-sonnet-4-6
  - GPT-4o
  - Gemini 2.5 Flash
進行 LLM-as-Judge 評分，輸出評審一致性統計。

執行：python scripts/evaluate_multimodel.py
"""

import json
import os
import time
from pathlib import Path
from collections import defaultdict

# ── 載入 API keys ──────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
for line in ENV_PATH.read_text().splitlines():
    k, _, v = line.partition("=")
    if k.strip():
        os.environ[k.strip()] = v.strip()

from anthropic import Anthropic
from openai import OpenAI
from google import genai as ggenai

claude_client = Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
gemini_client = ggenai.Client(api_key=os.environ["Google_AI_Studio_API_key"])

RESULTS_PATH = Path(__file__).parent / "experiment_results.json"
OUTPUT_PATH  = Path(__file__).parent / "multimodel_eval_results_v3.json"
AHP_WEIGHTS  = {"D1": 0.648, "D2": 0.230, "D3": 0.122}

# ── 評分 Prompt ───────────────────────────────────────────────────────────────
EVAL_SYSTEM = """你是一位嚴格、中立的保險推薦品質評審員。
依照 rubric 對 AI 保險顧問回應進行評分。每個維度只能給 1、2、3 分。
以 JSON 格式回覆，不含其他文字。"""

EVAL_PROMPT = """【用戶情境】{scenario_label}
【用戶問題】{message}
【AI 回應】{reply}

【評分 Rubric】
D1 需求覆蓋率（評分時僅判斷「是否回應了用戶需求」，條款細節的有無不影響本維度，由 D2 另行評分）
  1=未覆蓋核心需求：無方向、無具體商品、亦未說明無法滿足需求之原因
  2=部分覆蓋：有方向但缺具體商品，或對需求理解含糊籠統
  3=完整覆蓋，符合以下任一情況即可得 3 分（兩者互相獨立，(a) 不要求條款細節）：
     (a) 推薦了具名商品並說明適配原因（僅需商品名稱＋符合需求的理由，不要求條款層級細節，那是 D2 的評分範圍）
     (b) 正確判斷無符合需求之商品，且具體說明排除原因（如指出職業類別、年齡等具體限制條件），而非籠統建議諮詢業務員或未說明理由

D2 條款一致性
  1=無任何商品具體資訊，純靠業界通則  2=有商品名稱或保費數字，但欠缺條款細節  3=明確引用具體條款資訊或可核實保費

D3 資訊完整性
  1=無除外責任/限制揭露  2=揭露部分限制  3=充分揭露除外責任、職業/年齡限制、注意事項

回覆格式（數字只能 1/2/3）：
{{"D1": <分數>, "D2": <分數>, "D3": <分數>, "notes": "<判分依據，30字內>"}}"""


def parse_scores(raw: str) -> dict:
    try:
        raw = raw.strip()
        # 有時模型會在 JSON 前後加 markdown code block
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        s = json.loads(raw)
        d1, d2, d3 = int(s["D1"]), int(s["D2"]), int(s["D3"])
        w = round(d1 * AHP_WEIGHTS["D1"] + d2 * AHP_WEIGHTS["D2"] + d3 * AHP_WEIGHTS["D3"], 3)
        return {"D1": d1, "D2": d2, "D3": d3, "W_score": w, "notes": s.get("notes", "")}
    except Exception as e:
        return {"D1": None, "D2": None, "D3": None, "W_score": None, "notes": f"parse_error: {raw[:60]}"}


# ── 各模型呼叫 ─────────────────────────────────────────────────────────────────

def eval_claude(prompt: str) -> dict:
    r = claude_client.messages.create(
        model="claude-sonnet-4-6", max_tokens=200,
        system=EVAL_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_scores(r.content[0].text)


def eval_gpt4o(prompt: str) -> dict:
    r = openai_client.chat.completions.create(
        model="gpt-4o", max_tokens=200,
        messages=[
            {"role": "system", "content": EVAL_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return parse_scores(r.choices[0].message.content)


def eval_gemini(prompt: str) -> dict:
    full = EVAL_SYSTEM + "\n\n" + prompt
    r = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full,
    )
    return parse_scores(r.text)


EVALUATORS = {
    "claude": eval_claude,
    "gpt4o":  eval_gpt4o,
    "gemini": eval_gemini,
}


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    with open(RESULTS_PATH, encoding="utf-8") as f:
        experiments = json.load(f)

    results = []
    total = len(experiments) * len(EVALUATORS)
    done = 0

    for item in experiments:
        prompt = EVAL_PROMPT.format(
            scenario_label=item["scenario_label"],
            message=item["message"],
            reply=item["reply"],
        )
        row = {
            "scenario_id":    item["scenario_id"],
            "scenario_label": item["scenario_label"],
            "mode":           item["mode"],
            "run":            item["run"],
        }
        for ev_name, ev_fn in EVALUATORS.items():
            done += 1
            print(f"[{done}/{total}] {item['scenario_id']} | {item['mode']} | run{item['run']} | {ev_name}")
            scores = ev_fn(prompt)
            row[ev_name] = scores
            print(f"  D1={scores['D1']} D2={scores['D2']} D3={scores['D3']} W={scores['W_score']}  {scores['notes']}")
            time.sleep(0.5)

        results.append(row)

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！結果存至 {OUTPUT_PATH}")

    # ── 彙整統計 ──────────────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("三模型評審一致性彙整")
    print("="*70)

    # 各條件 × 各評審的平均 D1/D2/D3/W
    sums = defaultdict(lambda: defaultdict(lambda: {"D1":0,"D2":0,"D3":0,"W":0,"n":0}))
    for row in results:
        key = f"{row['scenario_id']}|{row['mode']}"
        for ev in EVALUATORS:
            s = row[ev]
            if s["D1"] is None:
                continue
            sums[key][ev]["D1"] += s["D1"]
            sums[key][ev]["D2"] += s["D2"]
            sums[key][ev]["D3"] += s["D3"]
            sums[key][ev]["W"]  += s["W_score"]
            sums[key][ev]["n"]  += 1

    print(f"\n{'情境|條件':<25} {'評審':^8} {'D1':>4} {'D2':>4} {'D3':>4} {'W-Score':>8}")
    print("-"*58)
    for key in sorted(sums.keys()):
        for ev in EVALUATORS:
            v = sums[key][ev]
            if v["n"] == 0:
                continue
            n = v["n"]
            print(f"{key:<25} {ev:^8} {v['D1']/n:>4.2f} {v['D2']/n:>4.2f} {v['D3']/n:>4.2f} {v['W']/n:>8.3f}")
        print()

    # 三模型 W-Score Pearson 相關
    print("\n=== 三模型 W-Score Pearson 相關係數 ===")
    import math
    ev_list = list(EVALUATORS.keys())
    w_by_ev = defaultdict(list)
    for row in results:
        for ev in ev_list:
            if row[ev]["W_score"] is not None:
                w_by_ev[ev].append(row[ev]["W_score"])

    def pearson(x, y):
        n = len(x)
        mx, my = sum(x)/n, sum(y)/n
        num = sum((a-mx)*(b-my) for a,b in zip(x,y))
        den = math.sqrt(sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))
        return round(num/den, 3) if den > 0 else 0

    for i in range(len(ev_list)):
        for j in range(i+1, len(ev_list)):
            a, b = ev_list[i], ev_list[j]
            r = pearson(w_by_ev[a], w_by_ev[b])
            print(f"  {a} × {b} : r = {r}")


if __name__ == "__main__":
    main()
