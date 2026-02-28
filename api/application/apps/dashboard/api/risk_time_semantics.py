from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends

from ...account.views import get_current_user_id
from ...settings.models import ExchangeAccount
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, BusinessException, StatusCode, success_response

router = APIRouter(tags=["Dashboard - Risk"])
logger = logging.getLogger(__name__)


def _try_parse_json(raw: Any) -> Any:
    # 中文注释：Redis 可能存字符串或 JSON；若能解析为 JSON 则返回结构化对象，否则返回原字符串。
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if not text:
        return raw
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return raw


@router.get(
    "/dashboard/risk/time_semantics/{exchange}/{symbol}/{trade_id}",
    response_model=BaseResponse[Any],
)
async def read_time_semantics(
    exchange: str,
    symbol: str,
    trade_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    读取 Redis 仓位时间耐受因子（risk:time_semantics:{exchange}:{symbol}:{trade_id}）

    - 动态路径参数：exchange / symbol / trade_id
    - 复用认证依赖：get_current_user_id
    - 复用统一响应封装：BaseResponse + success_response
    - 复用统一错误处理：BusinessException（由全局异常处理器转换为统一响应）
    """
    exchange = (exchange or "").lower().strip()
    symbol = (symbol or "").upper().strip()
    trade_id = (trade_id or "").lower().strip()

    if not exchange:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="exchange 不能为空")
    if not symbol:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="symbol 不能为空")
    if not trade_id:
        raise BusinessException(code=StatusCode.PARAM_ERROR, message="trade_id 不能为空")

    # 中文注释：仅允许读取当前用户已绑定且处于活跃状态的交易所数据，避免越权探测。
    account = await ExchangeAccount.get_or_none(
        user_id=user_id,
        exchange=exchange,
        is_active=True,
        is_deleted=False,
    )
    if not account:
        raise BusinessException(code=StatusCode.NOT_FOUND, message=f"Exchange account {exchange} not found or not active")

    redis_client = get_async_redis_client()
    key = f"risk:time_semantics:{exchange}:{symbol}:{trade_id}"

    try:
        raw = await redis_client.get(key)
        return success_response(_try_parse_json(raw))
    except BusinessException:
        raise
    except Exception:
        logger.exception(
            "读取仓位时间耐受因子失败：user_id=%s exchange=%s symbol=%s trade_id=%s key=%s",
            user_id,
            exchange,
            symbol,
            trade_id,
            key,
        )
        raise BusinessException(code=StatusCode.SERVER_ERROR, message="读取仓位时间耐受因子失败")
