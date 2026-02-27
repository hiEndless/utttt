from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.views import get_current_user_id
from ..models import AgentModelConfig, ModelProvider
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Settings - Agent Model Configs"])


class AgentModelConfigCreateIn(BaseModel):
    agent_name: str = Field(..., max_length=64)
    provider_id: str
    model_id: str = Field(..., max_length=128)
    is_active: bool = True


class AgentModelConfigOut(BaseModel):
    id: str
    agent_name: str
    provider_id: str
    provider: str
    model_id: str
    is_active: bool
    availability_status: str
    unavailable_reason: Optional[str] = None
    unavailable_until: Optional[datetime] = None
    last_check_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


@router.post("/settings/agent_model_configs", response_model=BaseResponse[AgentModelConfigOut])
async def create_agent_model_config(
    body: AgentModelConfigCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增或更新 Agent 模型配置（UPSERT 操作）。"""
    provider = await ModelProvider.get_or_none(
        id=body.provider_id, deleted_at__isnull=True, is_active=True
    )
    if not provider or (provider.user_id is not None and str(provider.user_id) != user_id):
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="provider not found or not allowed")

    existing = await AgentModelConfig.get_or_none(user_id=user_id, agent_name=body.agent_name)
    
    if existing:
        # 如果配置存在（无论是否被软删除），都进行更新
        existing.provider = provider
        existing.model_id = body.model_id
        existing.is_active = body.is_active
        existing.deleted_at = None  # 确保配置是激活状态
        await existing.save()
        obj = existing
    else:
        # 如果配置不存在，创建新配置
        obj = await AgentModelConfig.create(
            user_id=user_id,
            agent_name=body.agent_name,
            provider=provider,
            model_id=body.model_id,
            is_active=body.is_active,
        )

    return success_response(AgentModelConfigOut(
        id=str(obj.id),
        agent_name=obj.agent_name,
        provider_id=str(provider.id),
        provider=provider.provider,
        model_id=obj.model_id,
        is_active=obj.is_active,
        availability_status=obj.availability_status,
        unavailable_reason=obj.unavailable_reason,
        unavailable_until=obj.unavailable_until,
        last_check_at=obj.last_check_at,
        last_error_at=obj.last_error_at,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


@router.get("/settings/agent_model_configs", response_model=BaseResponse[list[AgentModelConfigOut]])
async def list_agent_model_configs(user_id: str = Depends(get_current_user_id)):
    """读取 Agent 模型配置列表。"""
    items = (
        await AgentModelConfig.filter(user_id=user_id, deleted_at__isnull=True)
        .prefetch_related("provider")
        .order_by("-created_at", "agent_name")
    )
    out: list[AgentModelConfigOut] = []
    for obj in items:
        provider = obj.provider
        out.append(
            AgentModelConfigOut(
                id=str(obj.id),
                agent_name=obj.agent_name,
                provider_id=str(provider.id),
                provider=provider.provider,
                model_id=obj.model_id,
                is_active=obj.is_active,
                availability_status=obj.availability_status,
                unavailable_reason=obj.unavailable_reason,
                unavailable_until=obj.unavailable_until,
                last_check_at=obj.last_check_at,
                last_error_at=obj.last_error_at,
                created_at=obj.created_at,
                updated_at=obj.updated_at,
            )
        )
    return success_response(out)


@router.get("/settings/agent_model_configs/{config_id}", response_model=BaseResponse[AgentModelConfigOut])
async def get_agent_model_config(config_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个 Agent 模型配置。"""
    obj = (
        await AgentModelConfig.filter(id=config_id, user_id=user_id, deleted_at__isnull=True)
        .prefetch_related("provider")
        .first()
    )
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    provider = obj.provider
    return success_response(AgentModelConfigOut(
        id=str(obj.id),
        agent_name=obj.agent_name,
        provider_id=str(provider.id),
        provider=provider.provider,
        model_id=obj.model_id,
        is_active=obj.is_active,
        availability_status=obj.availability_status,
        unavailable_reason=obj.unavailable_reason,
        unavailable_until=obj.unavailable_until,
        last_check_at=obj.last_check_at,
        last_error_at=obj.last_error_at,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))