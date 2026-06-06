"""設定配 — 約束求解器(投影法、確定性)。

以自由配的 100% baseline 為起點,套保經約束(下限/上限/必含),
用「鉗制 + 按 baseline 權重重分配」迭代求解。確定性、可解釋、無外部依賴。
"""
from __future__ import annotations

from .models import Adjustment, Allocation, AllocationResult, Constraint, IndependentNeeds

_BUCKETS = ("a", "b", "c")
_LABEL = {"a": "金融", "b": "保險", "c": "醫療"}
_EPS = 1e-9


def _bounds(constraints: list[Constraint]) -> tuple[dict[str, float], dict[str, float]]:
    """從約束推出每桶的下限 L 與上限 U。must_include 視為 floor;liquidity 不進三桶。"""
    lower = {k: 0.0 for k in _BUCKETS}
    upper = {k: 100.0 for k in _BUCKETS}
    for c in constraints:
        if not c.active or c.bucket is None:
            continue
        b = c.bucket.lower()
        if b not in _BUCKETS:
            continue
        if c.kind in ("floor", "must_include"):
            lower[b] = max(lower[b], c.value)
        elif c.kind == "cap":
            upper[b] = min(upper[b], c.value)
    return lower, upper


def solve(
    baseline: Allocation,
    constraints: list[Constraint],
    needs: IndependentNeeds | None = None,
) -> AllocationResult:
    """在約束下求解配置。回傳可解釋的 AllocationResult。"""
    lower, upper = _bounds(constraints)

    # 1) 可行性檢查
    sum_lower = sum(lower.values())
    sum_upper = sum(upper.values())
    if sum_lower > 100 + 1e-6:
        floors = "、".join(
            f"{_LABEL[k]}≥{int(lower[k])}%" for k in _BUCKETS if lower[k] > 0
        )
        return AllocationResult(
            allocation=baseline, baseline=baseline, needs=needs, feasible=False,
            error=f"下限總和 {int(sum_lower)}% 超過 100%（{floors}），無可行解。",
        )
    if sum_upper < 100 - 1e-6:
        caps = "、".join(
            f"{_LABEL[k]}≤{int(upper[k])}%" for k in _BUCKETS if upper[k] < 100
        )
        return AllocationResult(
            allocation=baseline, baseline=baseline, needs=needs, feasible=False,
            error=f"上限總和 {int(sum_upper)}% 不足 100%（{caps}），無可行解。",
        )

    # 2~3) 鉗制 + 按 baseline 權重重分配,迭代至收斂
    x = {k: float(getattr(baseline, k)) for k in _BUCKETS}
    weight = {k: float(getattr(baseline, k)) for k in _BUCKETS}
    for _ in range(1000):
        for k in _BUCKETS:
            x[k] = min(max(x[k], lower[k]), upper[k])
        residual = 100.0 - sum(x.values())
        if abs(residual) < _EPS:
            break
        if residual > 0:
            room = {k: upper[k] - x[k] for k in _BUCKETS}
        else:
            room = {k: x[k] - lower[k] for k in _BUCKETS}
        movable = [k for k in _BUCKETS if room[k] > 1e-12]
        if not movable:
            break
        wsum = sum(weight[k] for k in movable)
        for k in movable:
            share = (weight[k] / wsum) if wsum > 0 else 1.0 / len(movable)
            x[k] += residual * share

    for k in _BUCKETS:
        x[k] = min(max(x[k], lower[k]), upper[k])

    allocation = _round_alloc_to_100(x, lower, upper)

    # 4) 回報:binding / adjustments / explanation
    binding = _binding_constraints(allocation, constraints)
    adjustments = [
        Adjustment(
            bucket=k.upper(),
            baseline=float(getattr(baseline, k)),
            final=float(getattr(allocation, k)),
            delta=round(float(getattr(allocation, k)) - float(getattr(baseline, k)), 1),
        )
        for k in _BUCKETS
    ]
    explanation = _explain(binding, constraints)

    return AllocationResult(
        allocation=allocation,
        baseline=baseline,
        needs=needs,
        feasible=True,
        binding=binding,
        adjustments=adjustments,
        explanation=explanation,
    )


def _round_alloc_to_100(
    x: dict[str, float], lower: dict[str, float], upper: dict[str, float]
) -> Allocation:
    """整數化並把餘數補到仍在界內的桶,確保剛好 100。"""
    rounded = {k: int(round(v)) for k, v in x.items()}
    diff = 100 - sum(rounded.values())
    step = 1 if diff > 0 else -1
    order = sorted(_BUCKETS, key=lambda k: x[k], reverse=True)
    i = guard = 0
    while diff != 0 and guard < 1000:
        k = order[i % len(order)]
        nv = rounded[k] + step
        if lower[k] - 1e-9 <= nv <= upper[k] + 1e-9:
            rounded[k] = nv
            diff -= step
        i += 1
        guard += 1
    return Allocation(a=rounded["a"], b=rounded["b"], c=rounded["c"])


def _binding_constraints(allocation: Allocation, constraints: list[Constraint]) -> list[str]:
    """最終配置正好坐在某條件邊界上 → 該條件 binding。"""
    out: list[str] = []
    for c in constraints:
        if not c.active or c.bucket is None or c.value <= 0:
            continue
        v = float(getattr(allocation, c.bucket.lower(), 0.0))
        if abs(v - c.value) < 0.5:
            out.append(c.id)
    return out


def _explain(binding: list[str], constraints: list[Constraint]) -> str:
    parts: list[str] = []
    by_id = {c.id: c for c in constraints}
    for cid in binding:
        c = by_id.get(cid)
        if c is None or c.bucket is None:
            continue
        label = _LABEL.get(c.bucket.lower(), c.label)
        if c.kind == "cap":
            parts.append(f"{label}觸及上限 {int(c.value)}%")
        elif c.kind in ("floor", "must_include"):
            parts.append(f"{label}維持下限 {int(c.value)}%")
    if parts:
        return "、".join(parts) + ";其餘依基準比例重分配。"
    return "未觸及任何條件,維持自由配基準比例。"
