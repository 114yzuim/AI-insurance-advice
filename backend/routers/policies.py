from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from services.policy_service import (
    DEFAULT_PROFILE_ID,
    create_policy,
    create_policy_from_upload,
    create_profile,
    delete_policy,
    get_policy,
    list_profiles,
    list_policies,
    update_policy,
)

router = APIRouter()


class PolicyPayload(BaseModel):
    profile_id: str = Field(default=DEFAULT_PROFILE_ID)
    product_id: str = ""
    company_name: str
    policy_name: str
    policy_no: str = ""
    role: str = "主約"
    status: str = "有效"
    annual_premium: float = 0
    effective_date: str = ""
    source_document_id: int | None = None
    coverages: dict[str, float] = Field(default_factory=dict)
    riders: list[str] = Field(default_factory=list)


class ProfilePayload(BaseModel):
    id: str | None = None
    owner_name: str
    relation: str = "家人"


@router.get("")
def index(profile_id: str = Query(default=DEFAULT_PROFILE_ID)) -> dict[str, Any]:
    return list_policies(profile_id=profile_id)


@router.post("", status_code=201)
def store(payload: PolicyPayload) -> dict[str, Any]:
    policy_id = create_policy(payload.model_dump())
    policy = get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=500, detail="Policy was not created")
    return policy


@router.post("/upload", status_code=201)
def upload_policy(
    file: UploadFile = File(...),
    profile_id: str = Form(default=DEFAULT_PROFILE_ID),
) -> dict[str, Any]:
    if file.content_type and not (
        file.content_type == "application/pdf" or file.content_type.startswith("image/")
    ):
        raise HTTPException(status_code=400, detail="Only PDF or image files are supported")
    return create_policy_from_upload(file, profile_id=profile_id)


@router.get("/profiles")
def profiles() -> list[dict[str, Any]]:
    return list_profiles()


@router.post("/profiles", status_code=201)
def store_profile(payload: ProfilePayload) -> dict[str, Any]:
    return create_profile(payload.model_dump())


@router.get("/{policy_id}")
def show(policy_id: int) -> dict[str, Any]:
    policy = get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/{policy_id}")
def update(policy_id: int, payload: PolicyPayload) -> dict[str, Any]:
    policy = update_policy(policy_id, payload.model_dump())
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.delete("/{policy_id}")
def destroy(policy_id: int) -> dict[str, bool]:
    deleted = delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"deleted": True}
