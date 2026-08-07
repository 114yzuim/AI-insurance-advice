"""Product-agnostic retirement simulator."""

from .core import (
    ForwardResult,
    ReverseToRateResult,
    ReverseToSavingResult,
    YearlyAssetPoint,
    simulate_forward,
    simulate_reverse_to_rate,
    simulate_reverse_to_saving,
)
from .strategy import AllocationProjection, compare_allocations

__all__ = [
    "AllocationProjection",
    "ForwardResult",
    "ReverseToRateResult",
    "ReverseToSavingResult",
    "YearlyAssetPoint",
    "compare_allocations",
    "simulate_forward",
    "simulate_reverse_to_rate",
    "simulate_reverse_to_saving",
]
