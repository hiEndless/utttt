from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..account.views import get_current_user_id
from .models import AgentModelConfig, ExchangeAccount, ModelProvider, NotificationChannel

app = APIRouter()


def _mask_string(value: Optional[str], keep_start: int = 4, keep_end: int = 4) -> Optional[str]:
    if not value:
        return None
    v = str(value)
    if len(v) <= keep_start + keep_end:
        return "*" * len(v)
    return f"{v[:keep_start]}{'*' * 8}{v[-keep_end:]}"


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


class ExchangeAccountCreateIn(BaseModel):
    exchange: str = Field(..., max_length=32)
    api_key: Optional[str] = Field(default=None, max_length=256)
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = Field(default=None, max_length=128)
    api_label: Optional[str] = Field(default=None, max_length=64)
    is_read_only: bool = True
    is_active: bool = True


class ExchangeAccountOut(BaseModel):
    id: str
    exchange: str
    api_key_masked: Optional[str] = None
    api_label: Optional[str] = None
    is_read_only: bool
    is_active: bool
    has_api_secret: bool
    has_api_passphrase: bool
    created_at: datetime
    updated_at: datetime


@app.post("/settings/exchange_accounts", response_model=ExchangeAccountOut)
async def create_exchange_account(
    body: ExchangeAccountCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增交易所账户绑定信息（只返回脱敏信息）。"""
    existing = await ExchangeAccount.get_or_none(user_id=user_id, exchange=body.exchange)
    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail="该交易所已绑定，请先删除后再绑定")

    if existing and existing.is_deleted:
        existing.api_key = body.api_key
        existing.api_secret = body.api_secret
        existing.api_passphrase = body.api_passphrase
        existing.api_label = body.api_label
        existing.is_read_only = body.is_read_only
        existing.is_active = body.is_active
        existing.is_deleted = False
        existing.deleted_at = None
        await existing.save()
        obj = existing
    else:
        obj = await ExchangeAccount.create(
            user_id=user_id,
            exchange=body.exchange,
            api_key=body.api_key,
            api_secret=body.api_secret,
            api_passphrase=body.api_passphrase,
            api_label=body.api_label,
            is_read_only=body.is_read_only,
            is_active=body.is_active,
        )

    return ExchangeAccountOut(
        id=str(obj.id),
        exchange=obj.exchange,
        api_key_masked=_mask_string(obj.api_key),
        api_label=obj.api_label,
        is_read_only=obj.is_read_only,
        is_active=obj.is_active,
        has_api_secret=bool(obj.api_secret),
        has_api_passphrase=bool(obj.api_passphrase),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@app.get("/settings/exchange_accounts", response_model=list[ExchangeAccountOut])
async def list_exchange_accounts(user_id: str = Depends(get_current_user_id)):
    """读取当前用户的交易所账户绑定列表（只返回脱敏信息）。"""
    items = (
        await ExchangeAccount.filter(user_id=user_id, is_deleted=False)
        .order_by("-created_at", "exchange")
    )
    return [
        ExchangeAccountOut(
            id=str(obj.id),
            exchange=obj.exchange,
            api_key_masked=_mask_string(obj.api_key),
            api_label=obj.api_label,
            is_read_only=obj.is_read_only,
            is_active=obj.is_active,
            has_api_secret=bool(obj.api_secret),
            has_api_passphrase=bool(obj.api_passphrase),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
        for obj in items
    ]


@app.get("/settings/exchange_accounts/{account_id}", response_model=ExchangeAccountOut)
async def get_exchange_account(account_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个交易所账户绑定（只返回脱敏信息）。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise HTTPException(status_code=404, detail="not found")
    return ExchangeAccountOut(
        id=str(obj.id),
        exchange=obj.exchange,
        api_key_masked=_mask_string(obj.api_key),
        api_label=obj.api_label,
        is_read_only=obj.is_read_only,
        is_active=obj.is_active,
        has_api_secret=bool(obj.api_secret),
        has_api_passphrase=bool(obj.api_passphrase),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class ExchangeAccountUpdateIn(BaseModel):
    is_active: Optional[bool] = None
    api_label: Optional[str] = Field(default=None, max_length=64)


@app.patch("/settings/exchange_accounts/{account_id}", response_model=ExchangeAccountOut)
async def update_exchange_account(
    account_id: uuid.UUID,
    body: ExchangeAccountUpdateIn,
    user_id: str = Depends(get_current_user_id),
):
    """更新交易所账户状态（如启用/禁用）。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise HTTPException(status_code=404, detail="not found")

    if body.is_active is not None:
        if body.is_active:
            # 如果启用当前账户，需禁用该用户其他所有账户
            await ExchangeAccount.filter(user_id=user_id, is_deleted=False).update(is_active=False)
        obj.is_active = body.is_active

    if body.api_label is not None:
        obj.api_label = body.api_label

    await obj.save()
    
    return ExchangeAccountOut(
        id=str(obj.id),
        exchange=obj.exchange,
        api_key_masked=_mask_string(obj.api_key),
        api_label=obj.api_label,
        is_read_only=obj.is_read_only,
        is_active=obj.is_active,
        has_api_secret=bool(obj.api_secret),
        has_api_passphrase=bool(obj.api_passphrase),
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@app.delete("/settings/exchange_accounts/{account_id}")
async def delete_exchange_account(account_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """删除交易所账户绑定信息。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise HTTPException(status_code=404, detail="not found")
    
    # 执行软删除
    obj.is_deleted = True
    obj.deleted_at = datetime.now()
    await obj.save()
    
    return {"message": "Exchange account deleted successfully"}


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


@app.post("/settings/model_providers", response_model=ModelProviderOut)
async def create_model_provider(
    body: ModelProviderCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增模型供应商配置（只返回脱敏信息）。"""
    existing = await ModelProvider.get_or_none(
        user_id=user_id, provider=body.provider, is_active=True, deleted_at__isnull=True
    )
    if existing:
        raise HTTPException(status_code=400, detail="该供应商已存在启用配置")

    obj = await ModelProvider.create(
        user_id=user_id,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        is_active=body.is_active,
    )
    return ModelProviderOut(
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


@app.get("/settings/model_providers", response_model=list[ModelProviderOut])
async def list_model_providers(user_id: str = Depends(get_current_user_id)):
    """读取模型供应商配置列表（只返回脱敏信息）。"""
    items = (
        await ModelProvider.filter(user_id=user_id, deleted_at__isnull=True)
        .order_by("-created_at", "provider")
    )
    return [
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
    ]


@app.get("/settings/model_providers/{provider_id}", response_model=ModelProviderOut)
async def get_model_provider(provider_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个模型供应商配置（只返回脱敏信息）。"""
    obj = await ModelProvider.get_or_none(id=provider_id, user_id=user_id, deleted_at__isnull=True)
    if not obj:
        raise HTTPException(status_code=404, detail="not found")
    return ModelProviderOut(
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


@app.post("/settings/agent_model_configs", response_model=AgentModelConfigOut)
async def create_agent_model_config(
    body: AgentModelConfigCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增 Agent 模型配置。"""
    provider = await ModelProvider.get_or_none(
        id=body.provider_id, deleted_at__isnull=True, is_active=True
    )
    if not provider or (provider.user_id is not None and str(provider.user_id) != user_id):
        raise HTTPException(status_code=400, detail="provider not found or not allowed")

    existing = await AgentModelConfig.get_or_none(user_id=user_id, agent_name=body.agent_name)
    if existing and existing.deleted_at is None:
        raise HTTPException(status_code=400, detail="该 Agent 已存在配置")

    if existing and existing.deleted_at is not None:
        existing.provider = provider
        existing.model_id = body.model_id
        existing.is_active = body.is_active
        existing.deleted_at = None
        await existing.save()
        obj = existing
    else:
        obj = await AgentModelConfig.create(
            user_id=user_id,
            agent_name=body.agent_name,
            provider=provider,
            model_id=body.model_id,
            is_active=body.is_active,
        )

    return AgentModelConfigOut(
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


@app.get("/settings/agent_model_configs", response_model=list[AgentModelConfigOut])
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
    return out


@app.get("/settings/agent_model_configs/{config_id}", response_model=AgentModelConfigOut)
async def get_agent_model_config(config_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个 Agent 模型配置。"""
    obj = (
        await AgentModelConfig.filter(id=config_id, user_id=user_id, deleted_at__isnull=True)
        .prefetch_related("provider")
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="not found")
    provider = obj.provider
    return AgentModelConfigOut(
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


@app.post("/settings/notification_channels", response_model=NotificationChannelOut)
async def create_notification_channel(
    body: NotificationChannelCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增消息通知渠道（配置字段会在读取时脱敏）。"""
    obj = await NotificationChannel.create(
        user_id=user_id,
        channel_type=body.channel_type,
        name=body.name,
        config=body.config,
        is_active=body.is_active,
    )
    return NotificationChannelOut(
        id=str(obj.id),
        channel_type=obj.channel_type,
        name=obj.name,
        config=_redact_config(obj.config) if obj.config else None,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


@app.get("/settings/notification_channels", response_model=list[NotificationChannelOut])
async def list_notification_channels(user_id: str = Depends(get_current_user_id)):
    """读取消息通知渠道列表（配置字段会脱敏）。"""
    items = (
        await NotificationChannel.filter(user_id=user_id, is_deleted=False)
        .order_by("-created_at", "channel_type")
    )
    return [
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
    ]


@app.get("/settings/notification_channels/{channel_id}", response_model=NotificationChannelOut)
async def get_notification_channel(channel_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个消息通知渠道（配置字段会脱敏）。"""
    obj = await NotificationChannel.get_or_none(
        id=channel_id, user_id=user_id, is_deleted=False
    )
    if not obj:
        raise HTTPException(status_code=404, detail="not found")
    return NotificationChannelOut(
        id=str(obj.id),
        channel_type=obj.channel_type,
        name=obj.name,
        config=_redact_config(obj.config) if obj.config else None,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
