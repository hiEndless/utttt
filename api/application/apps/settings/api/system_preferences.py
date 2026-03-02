from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.views import get_current_user_id
from ..models import SystemPreference
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

router = APIRouter(tags=["Settings - System Preferences"])

def _coerce_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    return {"value": str(value)}


class SystemPreferenceUpsertIn(BaseModel):
    key: str = Field(..., max_length=64)
    value: Any = None


class SystemPreferenceOut(BaseModel):
    id: str
    key: str
    value: Any = None
    created_at: datetime
    updated_at: datetime


@router.post("/settings/system_preferences", response_model=BaseResponse[SystemPreferenceOut])
async def upsert_system_preference(
    body: SystemPreferenceUpsertIn,
    user_id: str = Depends(get_current_user_id),
):
    """创建或更新系统偏好（按 user_id + key 做 UPSERT）。"""
    key = body.key.strip()
    if not key:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="key is required")

    existing = await SystemPreference.get_or_none(user_id=user_id, key=key)
    if existing:
        existing.value = _coerce_json_value(body.value)
        await existing.save()
        obj = existing
    else:
        obj = await SystemPreference.create(
            user_id=user_id,
            key=key,
            value=_coerce_json_value(body.value),
        )

    return success_response(SystemPreferenceOut(
        id=str(obj.id),
        key=obj.key,
        value=obj.value,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


@router.get("/settings/system_preferences", response_model=BaseResponse[list[SystemPreferenceOut]])
async def list_system_preferences(user_id: str = Depends(get_current_user_id)):
    """读取系统偏好列表。"""
    items = await SystemPreference.filter(user_id=user_id).order_by("key")
    return success_response([
        SystemPreferenceOut(
            id=str(obj.id),
            key=obj.key,
            value=obj.value,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
        for obj in items
    ])


@router.get("/settings/system_preferences/{pref_id}", response_model=BaseResponse[SystemPreferenceOut])
async def get_system_preference(pref_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个系统偏好。"""
    obj = await SystemPreference.get_or_none(id=pref_id, user_id=user_id)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    return success_response(SystemPreferenceOut(
        id=str(obj.id),
        key=obj.key,
        value=obj.value,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))
