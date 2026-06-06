"""FastAPI router — 掛到 main.py:
    app.include_router(allocation_router, prefix="/api/allocation", tags=["allocation"])
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from .estimator import estimate
from .models import (
    Allocation,
    AllocationResult,
    CamelModel,
    ClientInputs,
    Constraint,
    IndependentNeeds,
)
from .solver import solve

router = APIRouter(tags=["allocation"])


class EstimateResponse(CamelModel):
    needs: IndependentNeeds
    allocation: Allocation


class SolveRequest(CamelModel):
    baseline: Optional[Allocation] = None
    client: Optional[ClientInputs] = None
    constraints: list[Constraint] = []


@router.post("/estimate", response_model=EstimateResponse)
def post_estimate(client: ClientInputs) -> EstimateResponse:
    needs, allocation = estimate(client)
    return EstimateResponse(needs=needs, allocation=allocation)


@router.post("/solve", response_model=AllocationResult)
def post_solve(req: SolveRequest) -> AllocationResult:
    needs: Optional[IndependentNeeds] = None
    baseline = req.baseline
    if baseline is None:
        if req.client is None:
            raise HTTPException(status_code=400, detail="must provide baseline or client")
        needs, baseline = estimate(req.client)
    return solve(baseline, req.constraints, needs=needs)
