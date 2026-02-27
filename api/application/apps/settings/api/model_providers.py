from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.views import get_current_user_id
from ..models import ModelProvider
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Settings - Model Providers"])


class ModelProviderCreateIn(BaseModel):
    provider: str = Field(..., max_length=64)
    base_url: str = Field(..., max_length=512)
    api_key: Optional[str] = None
    is_active: bool = True


class ModelProviderOut(BaseModel):
    id: str
    provider: str
    base_url: str
    is_active: bool
    availability_status: str
    unavailable_reason: Optional[str] = None
    unavailable_until: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


@router.post("/settings/model_providers", response_model=BaseResponse[ModelProviderOut])
async def create_model_provider(
    body: ModelProviderCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增模型供应商配置（只返回脱敏信息）。"""
    existing = await ModelProvider.get_or_none(
        user_id=user_id, provider=body.provider, deleted_at__isnull=True
    )
    if existing:
        raise BusinessException(code=StatusCode.PROVIDER_ALREADY_EXISTS)

    obj = await ModelProvider.create(
        user_id=user_id,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        is_active=body.is_active,
    )
    return success_response(ModelProviderOut(
        id=str(obj.id),
        provider=obj.provider,
        base_url=obj.base_url,
        is_active=obj.is_active,
        availability_status=obj.availability_status,
        unavailable_reason=obj.unavailable_reason,
        unavailable_until=obj.unavailable_until,
        last_check_at=obj.last_check_at,
        last_error_at=obj.last_error_at,
        has_api_key=bool(obj.api_key),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


@router.get("/settings/model_providers", response_model=BaseResponse[list[ModelProviderOut]])
async def list_model_providers(user_id: str = Depends(get_current_user_id)):
    """读取模型供应商配置列表（只返回脱敏信息）。"""
    items = (
        await ModelProvider.filter(user_id=user_id, deleted_at__isnull=True)
        .order_by("-created_at", "provider")
    )
    return success_response([
        ModelProviderOut(
            id=str(obj.id),
            provider=obj.provider,
            base_url=obj.base_url,
            is_active=obj.is_active,
            availability_status=obj.availability_status,
            unavailable_reason=obj.unavailable_reason,
            unavailable_until=obj.unavailable_until,
            last_check_at=obj.last_check_at,
            last_error_at=obj.last_error_at,
            has_api_key=bool(obj.api_key),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
        for obj in items
    ])


@router.get("/settings/model_providers/{provider_id}", response_model=BaseResponse[ModelProviderOut])
async def get_model_provider(provider_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个模型供应商配置（只返回脱敏信息）。"""
    obj = await ModelProvider.get_or_none(id=provider_id, user_id=user_id, deleted_at__isnull=True)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    return success_response(ModelProviderOut(
        id=str(obj.id),
        provider=obj.provider,
        base_url=obj.base_url,
        is_active=obj.is_active,
        availability_status=obj.availability_status,
        unavailable_reason=obj.unavailable_reason,
        unavailable_until=obj.unavailable_until,
        last_check_at=obj.last_check_at,
        last_error_at=obj.last_error_at,
        has_api_key=bool(obj.api_key),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


class ModelProviderUpdateIn(BaseModel):
    is_active: Optional[bool] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = Field(default=None, max_length=512)


@router.patch("/settings/model_providers/{provider_id}", response_model=BaseResponse[ModelProviderOut])
async def update_model_provider(
    provider_id: uuid.UUID,
    body: ModelProviderUpdateIn,
    user_id: str = Depends(get_current_user_id),
):
    """更新模型供应商配置（如启用/禁用、更新Key）。"""
    obj = await ModelProvider.get_or_none(id=provider_id, user_id=user_id, deleted_at__isnull=True)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)

    if body.is_active is not None:
        if body.is_active:
            # 检查是否有重复的同名供应商（包括已删除但未物理删除的）
            existing = await ModelProvider.get_or_none(
                user_id=user_id, provider=obj.provider, deleted_at__isnull=True
            )
            if existing and existing.id != obj.id:
                raise BusinessException(code=StatusCode.PROVIDER_ALREADY_EXISTS)
        obj.is_active = body.is_active

    if body.api_key is not None:
        obj.api_key = body.api_key
    
    if body.base_url is not None:
        obj.base_url = body.base_url

    await obj.save()
    
    return success_response(ModelProviderOut(
        id=str(obj.id),
        provider=obj.provider,
        base_url=obj.base_url,
        is_active=obj.is_active,
        availability_status=obj.availability_status,
        unavailable_reason=obj.unavailable_reason,
        unavailable_until=obj.unavailable_until,
        last_check_at=obj.last_check_at,
        last_error_at=obj.last_error_at,
        has_api_key=bool(obj.api_key),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


@router.delete("/settings/model_providers/{provider_id}", response_model=BaseResponse[dict])
async def delete_model_provider(provider_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """删除模型供应商配置。"""
    obj = await ModelProvider.get_or_none(id=provider_id, user_id=user_id, deleted_at__isnull=True)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    
    # 执行软删除
    obj.deleted_at = datetime.now()
    obj.is_active = False  # 同时禁用，防止唯一索引冲突
    await obj.save()
    
    return success_response({"message": "Model provider deleted successfully"})