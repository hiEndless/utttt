from __future__ import annotations

import logging
import json
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...account.views import get_current_user_id
from ...settings.models import ExchangeAccount
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, BusinessException, StatusCode, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Dashboard - Force Stream"])
logger = logging.getLogger(__name__)


def _try_parse_json(value: Any) -> Any:
    """尝试将 Redis 字符串值解析为 JSON；解析失败则原样返回字符串"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value
    try:
        return json.loads(s)
    except Exception:
        return value


def _try_parse_json_dict(d: Any) -> Any:
    """尝试对 Stream entry 的字段值做 JSON 解析（逐字段容错）"""
    if not isinstance(d, dict):
        return d
    parsed = {}
    for k, v in d.items():
        parsed[k] = _try_parse_json(v)
    return parsed


@router.get(
    "/dashboard/force_stream/{exchange}/{symbol}",
    response_model=BaseResponse[Any],
)
async def get_force_stream(
    exchange: str,
    symbol: str,
    limit: int = Query(50, ge=1, le=1000, description="返回的最新消息条数"),
    cursor: str | None = Query(None, description="游标（Stream entry id）；用于分页继续读取"),
    direction: str = Query("backward", pattern="^(backward|forward)$", description="分页方向：backward=从新到旧；forward=从旧到新"),
    user_id: str = Depends(get_current_user_id),
):
    """
    读取 Redis 中 force_stream:{exchange}:{symbol} 的值
    
    - 复用认证依赖：get_current_user_id
    - 复用统一响应封装：BaseResponse + success_response
    - 复用统一错误处理：BusinessException（由全局异常处理器转换为统一响应）
    """
    # 校验用户是否绑定了该交易所且账户处于活跃状态
    account = await ExchangeAccount.get_or_none(
        user_id=user_id,
        exchange=exchange,
        is_active=True,
        is_deleted=False,
    )
    if not account:
        raise BusinessException(
            code=StatusCode.NOT_FOUND,
            message=f"Exchange account {exchange} not found or not active",
        )

    redis_client = get_async_redis_client()
    key = f"force_stream:{exchange}:{symbol}"

    try:
        exists = await redis_client.exists(key)
    except Exception:
        logger.exception("检查 Redis key 是否存在失败：key=%s", key)
        raise BusinessException(code=StatusCode.SERVER_ERROR, message="读取 Redis 失败")

    if not exists:
        raise BusinessException(
            code=StatusCode.NOT_FOUND,
            message=f"force_stream 数据不存在：{exchange}/{symbol}",
        )

    try:
        if direction == "forward":
            # 中文注释：按时间正序读取；cursor 存在时会包含 cursor 对应的 entry，需要去重
            entries = await redis_client.xrange(key, min=cursor or "-", max="+", count=limit)
            if cursor and entries and entries[0][0] == cursor:
                entries = entries[1:]
            next_cursor = entries[-1][0] if entries else cursor
        else:
            # 中文注释：按“最新优先”读取；cursor 存在时会包含 cursor 对应的 entry，需要去重
            entries = await redis_client.xrevrange(key, max=cursor or "+", min="-", count=limit)
            if cursor and entries and entries[0][0] == cursor:
                entries = entries[1:]
            next_cursor = entries[-1][0] if entries else cursor
    except Exception:
        logger.exception("读取 Redis Stream 失败：key=%s cursor=%s direction=%s", key, cursor, direction)
        raise BusinessException(code=StatusCode.SERVER_ERROR, message="读取 Redis 失败")

    data = [{"id": entry_id, "data": _try_parse_json_dict(fields)} for entry_id, fields in entries]
    return success_response({"items": data, "next_cursor": next_cursor, "direction": direction})
