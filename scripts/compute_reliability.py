"""
計算跨三評審（Claude／GPT-4o／Gemini）的信度指標：Kendall's W 與 Krippendorff's α。
資料來源：v3（修正後 rubric）之四技術策略最終評分。
Pearson r 僅衡量兩兩線性相關，本腳本補充更適合「次序量表 × 多評審」的信度指標。

執行：python scripts/compute_reliability.py
"""
import json
import itertools
import math
from pathlib import Path

HERE = Path(__file__).parent
FILES = [
    "multimodel_eval_results_v3.json",
    "metadata_eval_results_v3.json",
    "sbert_eval_results_v3.json",
]
JUDGES = ["claude", "gpt4o", "gemini"]


def load_rows():
    rows = []
    for f in FILES:
        rows += json.load(open(HERE / f, encoding="utf-8"))
    return rows


def matrix(rows, field):
    """items (responses) × raters (judges)，過濾任一評審缺值的列。"""
    M = []
    for r in rows:
        rec = []
        ok = True
        for j in JUDGES:
            v = r[j].get(field)
            if v is None:
                ok = False
                break
            rec.append(v)
        if ok:
            M.append(rec)
    return M


def kendalls_w(M):
    n = len(M)
    m = len(JUDGES)
    cols = list(zip(*M))
    rank_cols = []
    for col in cols:
        order = sorted(range(len(col)), key=lambda i: col[i])
        ranks = [0] * len(col)
        i = 0
        while i < len(col):
            j = i
            while j + 1 < len(col) and col[order[j + 1]] == col[order[i]]:
                j += 1
            avg = sum(range(i + 1, j + 2)) / (j - i + 1)
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        rank_cols.append(ranks)
    Rrows = [sum(rank_cols[c][i] for c in range(m)) for i in range(n)]
    Rbar = sum(Rrows) / n
    S = sum((x - Rbar) ** 2 for x in Rrows)
    return 12 * S / (m ** 2 * (n ** 3 - n))


def krippendorff_alpha_interval(M):
    """區間度量版 Krippendorff's α。"""
    Do_num = Do_den = 0
    for row in M:
        for a, b in itertools.permutations(row, 2):
            Do_num += (a - b) ** 2
            Do_den += 1
    Do = Do_num / Do_den
    allv = [v for row in M for v in row]
    De_num = De_den = 0
    for a, b in itertools.permutations(allv, 2):
        De_num += (a - b) ** 2
        De_den += 1
    De = De_num / De_den
    return 1 - Do / De


def main():
    rows = load_rows()
    print(f"total responses: {len(rows)}  judges: {len(JUDGES)}\n")
    print(f"{'field':10s} {'n':>4} {'Kendall W':>11} {'Kripp alpha':>12}")
    for field in ["W_score", "D1", "D2", "D3"]:
        M = matrix(rows, field)
        print(f"{field:10s} {len(M):>4} {kendalls_w(M):>11.3f} {krippendorff_alpha_interval(M):>12.3f}")


if __name__ == "__main__":
    main()
