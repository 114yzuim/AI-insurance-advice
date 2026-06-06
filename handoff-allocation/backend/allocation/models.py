"""資料模型(對外契約) — pydantic v2。

兩層模型:
  - IndependentNeeds  (Layer 1 / 個別分析)  各自獨立、不加總 100
  - Allocation        (Layer 2)             加總 = 100

JSON 在網路上以 camelCase 呈現(對齊前端 TS),Python 內部用 snake_case。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

RiskTolerance = Literal["low", "mid", "high"]
Bucket = Literal["A", "B", "C"]
ConstraintKind = Literal["floor", "cap", "must_include", "liquidity"]


class CamelModel(BaseModel):
    """所有對外型別的基底:JSON 走 camelCase 別名,同時允許用欄位原名建構。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ClientInputs(CamelModel):
    """估算所需的客戶訊號。"""

    age: int = Field(..., ge=0, le=120)
    retire_age: int = Field(..., ge=0, le=120)
    monthly_investable: float = Field(0, ge=0)
    dependents: int = Field(0, ge=0)
    risk_tolerance: RiskTolerance = "mid"
    has_medical_coverage: bool = False
    has_life_coverage: bool = False


class IndependentNeeds(CamelModel):
    """Layer 1 / 個別分析:各桶純算的需求強度,互相獨立、刻意不加總 100。"""

    a: float
    b: float
    c: float

    @property
    def total(self) -> float:
        return self.a + self.b + self.c


class Allocation(CamelModel):
    """Layer 2:配置比例,a + b + c = 100。"""

    a: float
    b: float
    c: float

    @property
    def total(self) -> float:
        return self.a + self.b + self.c


class Constraint(CamelModel):
    """設定配的單一條件。"""

    id: str
    label: str
    kind: ConstraintKind
    bucket: Optional[Bucket] = None
    value: float = 0
    active: bool = True


class Adjustment(CamelModel):
    """設定配求解後,單一桶相對 baseline 的位移。"""

    bucket: Bucket
    baseline: float
    final: float
    delta: float


class AllocationResult(CamelModel):
    """設定配求解結果 — 可解釋。"""

    allocation: Allocation
    baseline: Allocation
    needs: Optional[IndependentNeeds] = None
    feasible: bool = True
    binding: list[str] = Field(default_factory=list)
    adjustments: list[Adjustment] = Field(default_factory=list)
    explanation: str = ""
    error: Optional[str] = None
