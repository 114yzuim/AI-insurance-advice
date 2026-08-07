"""
彙整三條件（sbert_only / no_rag / pdf_rag）的最終統計數字，供論文 §4 表 3/表 4 使用。
讀取：sbert_eval_results.json（沿用，未變動）+ multimodel_eval_results.json（本次新跑）
輸出：純文字報表（不寫檔，供人工抄入論文表格）
"""
import json
import math
from pathlib import Path
from collections import defaultdict

DIR = Path(__file__).parent
AHP_WEIGHTS = {"D1": 0.648, "D2": 0.230, "D3": 0.122}
EVALUATORS = ["claude", "gpt4o", "gemini"]

sbert = json.load(open(DIR / "sbert_eval_results.json", encoding="utf-8"))
multimodel = json.load(open(DIR / "multimodel_eval_results.json", encoding="utf-8"))

all_rows = sbert + multimodel  # each row has claude/gpt4o/gemini sub-dicts with D1/D2/D3/W_score


def w_score(d1, d2, d3):
    return d1 * AHP_WEIGHTS["D1"] + d2 * AHP_WEIGHTS["D2"] + d3 * AHP_WEIGHTS["D3"]


# ---- per (scenario, mode) average across runs & evaluators ----
by_scen_mode = defaultdict(lambda: {"D1": [], "D2": [], "D3": [], "W": []})
for row in all_rows:
    key = (row["scenario_id"], row["mode"])
    for ev in EVALUATORS:
        s = row[ev]
        by_scen_mode[key]["D1"].append(s["D1"])
        by_scen_mode[key]["D2"].append(s["D2"])
        by_scen_mode[key]["D3"].append(s["D3"])
        by_scen_mode[key]["W"].append(s["W_score"])

print("=" * 80)
print("表 4：各情境各條件評分細項（三模型均值，跨 3 run）")
print("=" * 80)
scen_order = ["S01", "S08", "S13"]
mode_order = ["sbert_only", "no_rag", "pdf_rag"]
scen_mode_summary = {}
for scen in scen_order:
    for mode in mode_order:
        v = by_scen_mode[(scen, mode)]
        n = len(v["D1"])
        d1, d2, d3 = sum(v["D1"]) / n, sum(v["D2"]) / n, sum(v["D3"]) / n
        unweighted = d1 + d2 + d3
        w = sum(v["W"]) / n
        passed = "✓" if unweighted >= 7 else "—"
        scen_mode_summary[(scen, mode)] = (d1, d2, d3, unweighted, w, passed)
        print(f"{scen} | {mode:11s} | D1={d1:.2f} D2={d2:.2f} D3={d3:.2f} | 未加權={unweighted:.2f} | W={w:.3f} | 達標={passed} (n={n})")
    print()

# ---- per mode overall average (across 3 scenarios) ----
print("=" * 80)
print("表 3：三條件對照結果摘要（3 情境 × 三模型評審均值）")
print("=" * 80)
mode_summary = {}
for mode in mode_order:
    d1s = [scen_mode_summary[(s, mode)][0] for s in scen_order]
    d2s = [scen_mode_summary[(s, mode)][1] for s in scen_order]
    d3s = [scen_mode_summary[(s, mode)][2] for s in scen_order]
    ws  = [scen_mode_summary[(s, mode)][4] for s in scen_order]
    passes = sum(1 for s in scen_order if scen_mode_summary[(s, mode)][5] == "✓")
    d1m, d2m, d3m = sum(d1s)/3, sum(d2s)/3, sum(d3s)/3
    unweighted = d1m + d2m + d3m
    wm = sum(ws)/3
    mode_summary[mode] = (d1m, d2m, d3m, unweighted, wm, passes)
    print(f"{mode:11s} | D1={d1m:.2f} D2={d2m:.2f} D3={d3m:.2f} | 未加權={unweighted:.2f} | W-Score={wm:.3f} | 達標={passes}/3")

print()
print(f"W-Score 排序: " + " < ".join(f"{m}({mode_summary[m][4]:.3f})" for m in sorted(mode_order, key=lambda m: mode_summary[m][4])))

# ---- Pearson r between evaluators (no_rag + pdf_rag only, N=18) ----
print()
print("=" * 80)
print("三廠商評審一致性（no_rag + pdf_rag, N=18, W-Score）")
print("=" * 80)
w_by_ev = defaultdict(list)
for row in multimodel:
    for ev in EVALUATORS:
        w_by_ev[ev].append(row[ev]["W_score"])

def pearson(x, y):
    n = len(x)
    mx, my = sum(x)/n, sum(y)/n
    num = sum((a-mx)*(b-my) for a, b in zip(x, y))
    den = math.sqrt(sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))
    return round(num/den, 3) if den > 0 else 0

pairs = [("claude","gpt4o"), ("claude","gemini"), ("gpt4o","gemini")]
for a, b in pairs:
    r = pearson(w_by_ev[a], w_by_ev[b])
    print(f"  {a} × {b} : r = {r}")

# ---- per-evaluator W-score mean (no_rag+pdf_rag combined, N=18) — self-enhancement bias check ----
print()
print("各評審模型 W-Score 均值（no_rag + pdf_rag 合計, N=18）")
for ev in EVALUATORS:
    vals = w_by_ev[ev]
    print(f"  {ev}: {sum(vals)/len(vals):.3f}")

# sbert_only: check zero-variance note (no Pearson, all 3 evaluators identical per scenario per original methodology)
print()
print("sbert_only 三廠商評審是否完全一致（無變異）：")
for scen in scen_order:
    v = by_scen_mode[(scen, "sbert_only")]
    print(f"  {scen}: D2 values={v['D2']}  D3 values={v['D3']}  (全部相同={len(set(v['D2']))==1 and len(set(v['D3']))==1})")
