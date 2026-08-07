"""自由配 — 兩層估算(規則式、確定性)。

Layer 1  individual_needs(client)  純算各桶需求,各自獨立、不加總 100
Layer 2  free_allocate(needs)      把三個獨立需求正規化成加總 100% 的配置

依 2026-05-01 會議定調:個別分析(mode one)是自由配(mode two)的「背景輸入」,
而非各自最佳化的最終結果;自由配才是把它們整合成 100% 的主要輸出。

常數為「合理預設起點」,日後可替換為保經的真實規則/對照表,契約不變。
"""
from __future__ import annotations

from .models import Allocation, ClientInputs, IndependentNeeds

_BUCKETS = ("a", "b", "c")


def individual_needs(client: ClientInputs) -> IndependentNeeds:
    """Layer 1:各桶各自獨立純算(刻意不正規化)。"""
    years_to_retire = max(0, client.retire_age - client.age)

    need_a = 30 + min(years_to_retire, 30)                       # 金融:年期越長 → 純需求越高
    need_b = 18 + client.dependents * 3 + (6 if client.risk_tolerance == "low" else 0)  # 保險
    need_c = 8 + max(0, client.age - 40) * 0.4 + (0 if client.has_medical_coverage else 6)  # 醫療

    return IndependentNeeds(a=float(need_a), b=float(need_b), c=float(need_c))


def free_allocate(needs: IndependentNeeds) -> Allocation:
    """Layer 2:把獨立需求正規化成加總 100% 的配置。"""
    total = needs.a + needs.b + needs.c
    if total <= 0:
        return Allocation(a=34, b=33, c=33)  # 退化情況:均分
    raw = {k: 100.0 * getattr(needs, k) / total for k in _BUCKETS}
    return _round_to_100(raw)


def estimate(client: ClientInputs) -> tuple[IndependentNeeds, Allocation]:
    """一次跑完兩層:回 (個別需求, 自由配)。"""
    needs = individual_needs(client)
    return needs, free_allocate(needs)


def _round_to_100(raw: dict[str, float]) -> Allocation:
    """四捨五入到整數後,把餘數補到(原始值)最大的桶,確保剛好加總 100。"""
    rounded = {k: int(round(v)) for k, v in raw.items()}
    diff = 100 - sum(rounded.values())
    if diff != 0:
        biggest = max(raw, key=lambda k: raw[k])
        rounded[biggest] += diff
    return Allocation(a=rounded["a"], b=rounded["b"], c=rounded["c"])
