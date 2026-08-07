"""
三模型交叉評審 — 續跑腳本（因 Anthropic 額度中斷後使用）

evaluate_multimodel.py 在第 31/54 次呼叫（S08 pdf_rag run2 | claude）時
因 Anthropic API 額度用盡而中斷。已完成的前 30 次呼叫（10 筆 row）已從
log 還原至 scripts/multimodel_recovered_partial.json，不重打。

本腳本只處理剩餘 8 筆 row（S08 pdf_rag run2/run3、S13 全部 6 筆），
跑完後與已還原的 10 筆合併，輸出最終 scripts/multimodel_eval_results.json。

執行前請確認 Anthropic API 額度已加值。
執行：python scripts/evaluate_multimodel_resume.py
"""

import json
import os
import time
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / "backend" / ".env"
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    k, _, v = line.partition("=")
    if k.strip():
        os.environ[k.strip()] = v.strip()

from anthropic import Anthropic
from openai import OpenAI
from google import genai as ggenai

claude_client = Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
gemini_client = ggenai.Client(api_key=os.environ["Google_AI_Studio_API_key"])

RESULTS_PATH    = Path(__file__).parent / "experiment_results.json"
RECOVERED_PATH  = Path(__file__).parent / "multimodel_recovered_partial.json"
OUTPUT_PATH     = Path(__file__).parent / "multimodel_eval_results.json"
AHP_WEIGHTS     = {"D1": 0.648, "D2": 0.230, "D3": 0.122}

EVAL_SYSTEM = """你是一位嚴格、中立的保險推薦品質評審員。
依照 rubric 對 AI 保險顧問回應進行評分。每個維度只能給 1、2、3 分。
以 JSON 格式回覆，不含其他文字。"""

EVAL_PROMPT = """【用戶情境】{scenario_label}
【用戶問題】{message}
【AI 回應】{reply}

【評分 Rubric】
D1 需求覆蓋率
  1=未覆蓋核心需求  2=部分覆蓋，有方向但缺具體商品  3=完整覆蓋，推薦了具名商品並說明適配原因

D2 條款一致性
  1=無任何商品具體資訊，純靠業界通則  2=有商品名稱或保費數字，但欠缺條款細節  3=明確引用具體條款資訊或可核實保費

D3 資訊完整性
  1=無除外責任/限制揭露  2=揭露部分限制  3=充分揭露除外責任、職業/年齡限制、注意事項

回覆格式（數字只能 1/2/3）：
{{"D1": <分數>, "D2": <分數>, "D3": <分數>, "notes": "<判分依據，30字內>"}}"""


def parse_scores(raw: str) -> dict:
    try:
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        s = json.loads(raw)
        d1, d2, d3 = int(s["D1"]), int(s["D2"]), int(s["D3"])
        w = round(d1 * AHP_WEIGHTS["D1"] + d2 * AHP_WEIGHTS["D2"] + d3 * AHP_WEIGHTS["D3"], 3)
        return {"D1": d1, "D2": d2, "D3": d3, "W_score": w, "notes": s.get("notes", "")}
    except Exception as e:
        return {"D1": None, "D2": None, "D3": None, "W_score": None, "notes": f"parse_error: {raw[:60]}"}


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


EVALUATORS = {"claude": eval_claude, "gpt4o": eval_gpt4o, "gemini": eval_gemini}


def main():
    experiments = json.load(open(RESULTS_PATH, encoding="utf-8"))
    recovered = json.load(open(RECOVERED_PATH, encoding="utf-8"))
    done_keys = {(r["scenario_id"], r["mode"], r["run"]) for r in recovered}

    remaining = [e for e in experiments if (e["scenario_id"], e["mode"], e["run"]) not in done_keys]
    print(f"已還原 {len(recovered)} 筆，剩餘需評審 {len(remaining)} 筆 x 3 評審 = {len(remaining)*3} 次呼叫")

    new_rows = []
    total = len(remaining) * len(EVALUATORS)
    done = 0
    for item in remaining:
        prompt = EVAL_PROMPT.format(
            scenario_label=item["scenario_label"],
            message=item["message"],
            reply=item["reply"],
        )
        row = {
            "scenario_id": item["scenario_id"],
            "scenario_label": item["scenario_label"],
            "mode": item["mode"],
            "run": item["run"],
        }
        for ev_name, ev_fn in EVALUATORS.items():
            done += 1
            print(f"[{done}/{total}] {item['scenario_id']} | {item['mode']} | run{item['run']} | {ev_name}")
            scores = ev_fn(prompt)
            row[ev_name] = scores
            print(f"  D1={scores['D1']} D2={scores['D2']} D3={scores['D3']} W={scores['W_score']}  {scores['notes']}")
            time.sleep(0.5)
        new_rows.append(row)

    final = recovered + new_rows
    # restore original experiment order
    order = {(e["scenario_id"], e["mode"], e["run"]): i for i, e in enumerate(experiments)}
    final.sort(key=lambda r: order[(r["scenario_id"], r["mode"], r["run"])])

    OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成！合併後共 {len(final)} 筆，結果存至 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
