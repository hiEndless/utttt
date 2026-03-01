from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...account.views import get_current_user_id
from ..models import ExchangeAccount
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Settings - Exchange Accounts"])

def _mask_string(value: Optional[str], keep_start: int = 4, keep_end: int = 4) -> Optional[str]:
    if not value:
        return None
    v = str(value)
    if len(v) <= keep_start + keep_end:
        return "*" * len(v)
    return f"{v[:keep_start]}{'*' * 8}{v[-keep_end:]}"


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


@router.post("/settings/exchange_accounts", response_model=BaseResponse[ExchangeAccountOut])
async def create_exchange_account(
    body: ExchangeAccountCreateIn,
    user_id: str = Depends(get_current_user_id),
):
    """新增交易所账户绑定信息（只返回脱敏信息）。"""
    existing = await ExchangeAccount.get_or_none(user_id=user_id, exchange=body.exchange)
    if existing and not existing.is_deleted:
        raise BusinessException(code=StatusCode.ACCOUNT_ALREADY_BOUND)

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

    return success_response(ExchangeAccountOut(
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
    ))


@router.get("/settings/exchange_accounts", response_model=BaseResponse[list[ExchangeAccountOut]])
async def list_exchange_accounts(user_id: str = Depends(get_current_user_id)):
    """读取当前用户的交易所账户绑定列表（只返回脱敏信息）。"""
    items = (
        await ExchangeAccount.filter(user_id=user_id, is_deleted=False)
        .order_by("-created_at", "exchange")
    )
    return success_response([
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
    ])


@router.get("/settings/exchange_accounts/{account_id}", response_model=BaseResponse[ExchangeAccountOut])
async def get_exchange_account(account_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """读取单个交易所账户绑定（只返回脱敏信息）。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    return success_response(ExchangeAccountOut(
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
    ))


class ExchangeAccountUpdateIn(BaseModel):
    is_active: Optional[bool] = None
    api_label: Optional[str] = Field(default=None, max_length=64)


def _active_exchange_key(exchange: str) -> str:
    return f"exchange_account:{str(exchange).strip().lower()}:active"


@router.patch("/settings/exchange_accounts/{account_id}", response_model=BaseResponse[ExchangeAccountOut])
async def update_exchange_account(
    account_id: uuid.UUID,
    body: ExchangeAccountUpdateIn,
    user_id: str = Depends(get_current_user_id),
):
    """更新交易所账户状态（如启用/禁用）。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)

    if body.is_active is not None:
        if body.is_active:
            # 中文注释：多交易所并行采集场景下，仅需保证“同一交易所”只有一个激活账户
            await ExchangeAccount.filter(user_id=user_id, exchange=obj.exchange, is_deleted=False).update(is_active=False)
        obj.is_active = body.is_active

    if body.api_label is not None:
        obj.api_label = body.api_label

    await obj.save()

    if body.is_active is not None:
        redis_client = get_async_redis_client()

        exchange_key = _active_exchange_key(obj.exchange)
        redis_changed = False

        try:
            before_raw = await redis_client.get(exchange_key)
        except Exception:
            before_raw = None

        if obj.is_active:
            if not obj.api_key or not obj.api_secret:
                raise BusinessException(code=StatusCode.PARAM_ERROR, message="激活失败：缺少 API Key 或 API Secret")

            payload = {
                "exchange_account_id": str(obj.id),
                "user_id": str(obj.user_id),
                "exchange": obj.exchange,
                "api_key": obj.api_key,
                "api_secret": obj.api_secret,
                "is_read_only": bool(obj.is_read_only),
            }
            value = json.dumps(payload, sort_keys=True)
            try:
                await redis_client.set(exchange_key, value)
            except Exception:
                raise BusinessException(code=StatusCode.SERVER_ERROR, message="更新 Redis 失败，请稍后重试")
            redis_changed = before_raw != value
        else:
            try:
                cur = await redis_client.get(exchange_key)
            except Exception:
                cur = None

            should_delete = True
            if cur:
                try:
                    cur_obj = json.loads(cur)
                    if cur_obj.get("exchange_account_id") and str(cur_obj.get("exchange_account_id")) != str(obj.id):
                        should_delete = False
                except Exception:
                    should_delete = True

            if should_delete:
                try:
                    await redis_client.delete(exchange_key)
                except Exception:
                    pass
                redis_changed = bool(before_raw)
    
    return success_response(ExchangeAccountOut(
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
    ))


@router.delete("/settings/exchange_accounts/{account_id}", response_model=BaseResponse[dict])
async def delete_exchange_account(account_id: uuid.UUID, user_id: str = Depends(get_current_user_id)):
    """删除交易所账户绑定信息。"""
    obj = await ExchangeAccount.get_or_none(id=account_id, user_id=user_id, is_deleted=False)
    if not obj:
        raise BusinessException(code=StatusCode.NOT_FOUND)
    
    # 执行软删除
    obj.is_deleted = True
    obj.deleted_at = datetime.now()
    await obj.save()
    
    return success_response({"message": "Exchange account deleted successfully"})
