from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.auth import get_current_user_id
from ..models import NotificationChannel
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Settings - Notification Channels"])


def _redact_config(value: Any) -> Any:
    sensitive_keys = {
        "token",
        "secret",
        "webhook",
        "password",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "passphrase",
    }
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if str(k).strip().lower() in sensitive_keys:
                out[k] = "***"
            else:
                out[k] = _redact_config(v)
        return out
    if isinstance(value, list):
        return [_redact_config(v) for v in value]
    return value


class NotificationChannelCreateIn(BaseModel):
    channel_type: str = Field(..., max_length=32)
    name: Optional[str] = Field(default=None, max_length=64)
    config: Optional[dict[str, Any]] = None
    is_active: bool = True


class NotificationChannelOut(BaseModel):
    id: str
    channel_type: str
    name: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@router.post("/settings/notification_channels", response_model=BaseResponse[NotificationChannelOut])
async def upsert_notification_channel(
    body: NotificationChannelCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """创建或更新消息通知渠道（配置字段会在读取时脱敏）。
    
    如果用户已存在相同 channel_type 的渠道，则更新该渠道；
    否则，创建一个新渠道。
    """
    # Check if a channel with the same type already exists for the user
    existing_channel = await NotificationChannel.get_or_none(
        user_id=user_id, 
        channel_type=body.channel_type, 
        is_deleted=False
    )
    
    if existing_channel:
        # Update existing channel
        existing_channel.name = body.name
        existing_channel.config = body.config
        existing_channel.is_active = body.is_active
        await existing_channel.save()
        obj = existing_channel
    else:
        # Create new channel
        obj = await NotificationChannel.create(
            user_id=user_id,
            channel_type=body.channel_type,
            name=body.name,
            config=body.config,
            is_active=body.is_active,
        )
    
    return success_response(NotificationChannelOut(
        id=str(obj.id),
        channel_type=obj.channel_type,
        name=obj.name,
        config=_redact_config(obj.config) if obj.config else None,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))


@router.get("/settings/notification_channels", response_model=BaseResponse[list[NotificationChannelOut]])
async def list_notification_channels(user_id: str = Depends(get_current_user_id)):
    """读取消息通知渠道列表（配置字段会脱敏）。"""
    items = (
        await NotificationChannel.filter(user_id=user_id, is_deleted=False)
        .order_by("-created_at", "channel_type")
    )
    return success_response([
        NotificationChannelOut(
            id=str(obj.id),
            channel_type=obj.channel_type,
            name=obj.name,
            config=_redact_config(obj.config) if obj.config else None,
            is_active=obj.is_active,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
        for obj in items
    ])


@router.get("/settings/notification_channels/{channel_id}", response_model=BaseResponse[NotificationChannelOut])
async def get_notification_channel(channel_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个消息通知渠道（配置字段会脱敏）。"""
    obj = await NotificationChannel.get_or_none(
        id=channel_id, user_id=user_id, is_deleted=False
    )
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    return success_response(NotificationChannelOut(
        id=str(obj.id),
        channel_type=obj.channel_type,
        name=obj.name,
        config=_redact_config(obj.config) if obj.config else None,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    ))
