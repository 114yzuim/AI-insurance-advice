"""自由配 / 設定配 配置模組。

公開 API:
    estimate(client)            -> (IndependentNeeds, Allocation)   自由配(兩層)
    individual_needs(client)    -> IndependentNeeds                 Layer 1 個別分析
    free_allocate(needs)        -> Allocation                       Layer 2 整合 100%
    solve(baseline, constraints)-> AllocationResult                 設定配
    default_constraints()       -> list[Constraint]                 原型預設 4 條
"""
from .estimator import estimate, free_allocate, individual_needs
from .models import (
    Allocation,
    AllocationResult,
    ClientInputs,
    Constraint,
    IndependentNeeds,
)
from .solver import solve


def default_constraints() -> list[Constraint]:
    """對應原型「設定配」的預設條件清單(可作為前端初始值)。"""
    return [
        Constraint(id="ins_floor", label="保險佔比下限", kind="floor", bucket="B", value=25, active=True),
        Constraint(id="med_must", label="必含醫療 / 長照", kind="must_include", bucket="C", value=10, active=True),
        Constraint(id="fin_cap", label="金融佔比上限", kind="cap", bucket="A", value=60, active=True),
        Constraint(id="liquidity", label="流動性保留 ≥6個月", kind="liquidity", bucket=None, value=6, active=False),
    ]


__all__ = [
    "estimate", "individual_needs", "free_allocate", "solve", "default_constraints",
    "ClientInputs", "IndependentNeeds", "Allocation", "Constraint", "AllocationResult",
]
