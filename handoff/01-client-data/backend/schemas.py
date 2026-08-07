"""Pydantic request/response models for API validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Clients ──────────────────────────────────────────────

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str | None = None
    phone: str | None = None
    age: int = Field(..., ge=18, le=120)
    gender: str | None = None
    family_status: str | None = None
    children_count: int = Field(default=0, ge=0)
    children_ages: list[int] = Field(default_factory=list)
    occupation: str | None = None
    target_retire_age: int | None = Field(default=65, ge=30, le=100)
    life_expectancy: int | None = Field(default=85, ge=50, le=120)
    risk_tolerance: str | None = None
    planning_goals: list[str] = Field(default_factory=list)
    # A = 投資 / B = 保險 / C = 失能長照
    selected_modules: list[str] = Field(default_factory=lambda: ["A"])
    is_joint_plan: bool = False
    spouse_name: str | None = None
    spouse_age: int | None = None
    spouse_gender: str | None = None
    spouse_retire_age: int | None = None
    spouse_life_expectancy: int | None = Field(default=85)
    monthly_income: float = Field(default=0, ge=0)
    monthly_expense: float = Field(default=0, ge=0)
    current_assets: float = Field(default=0, ge=0)
    current_liabilities: float = Field(default=0, ge=0)
    monthly_investable: float = Field(default=0, ge=0)
    target_retire_monthly_expense: float = Field(default=0, ge=0)
    existing_insurance_annual: float = Field(default=0, ge=0)


class ClientUpdate(ClientCreate):
    pass


# ── Chat ─────────────────────────────────────────────────

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    pageContext: str | None = None
    pageData: dict | None = None
