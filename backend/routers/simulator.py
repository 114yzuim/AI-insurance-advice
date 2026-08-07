"""Stateless retirement simulator — no DB dependency.

Uses adapter/inputs_adapter.py which replaces the original _resolve_ages_and_assets()
DB call with a plain-dict resolver. All inputs come directly from the request body.
"""
from typing import Any

from fastapi import APIRouter, HTTPException

from adapter.inputs_adapter import resolve_inputs, run_forward, run_reverse_saving, run_reverse_rate
from engine import constants as C

router = APIRouter()


@router.get("/defaults")
def get_defaults() -> dict[str, Any]:
    return {
        "annual_rate": C.DEFAULT_ANNUAL_RATE,
        "inflation_rate": C.DEFAULT_INFLATION_RATE,
        "rate_bounds": {"min": C.RATE_BOUNDS[0], "max": C.RATE_BOUNDS[1]},
        "category_rates": C.module_category_rates(),
    }


@router.post("/forward")
def forward(payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 1: savings plan → future value, withdrawable income, achievement ratio + yearly curve."""
    inputs = resolve_inputs(record={}, overrides=payload)
    try:
        return run_forward(
            inputs,
            annual_rate=payload.get("annual_rate"),
            inflation_rate=payload.get("inflation_rate"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reverse-saving")
def reverse_saving(payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 2: target → required monthly saving."""
    inputs = resolve_inputs(record={}, overrides=payload)
    target_kind = str(payload.get("target_kind") or "monthly")
    target_corpus = float(payload.get("target_corpus_twd") or 0)
    try:
        return run_reverse_saving(
            inputs,
            target_kind=target_kind,
            target_corpus_twd=target_corpus,
            annual_rate=payload.get("annual_rate"),
            inflation_rate=payload.get("inflation_rate"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reverse-rate")
def reverse_rate(payload: dict[str, Any]) -> dict[str, Any]:
    """Mode 3: savings + withdrawal target → required annual rate (bisection)."""
    inputs = resolve_inputs(record={}, overrides=payload)
    try:
        return run_reverse_rate(
            inputs,
            inflation_rate=payload.get("inflation_rate"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
