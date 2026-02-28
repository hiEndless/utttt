from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, StatusCode, BusinessException, success_response

# 路由（无需 JWT 认证）
router = APIRouter(tags=["Dashboard - Background"])

# 支持的全周期 interval 列表
ALL_INTERVALS: List[str] = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]


def _decode_value(raw: Optional[str]) -> Any:
    """尝试将 Redis 中的字符串解码为 JSON；失败则返回原始字符串或 None"""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return ""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


@router.get("/dashboard/background/kline/{exchange}/{symbol}/{interval}", response_model=BaseResponse[Any])
async def read_background(exchange: str, symbol: str, interval: str):
    """
    读取 Redis 中某个交易对的周期解读信息
    - 单周期：background:{exchange}:{symbol}:{interval}
    - 全周期：当 interval == 'all' 时，一次性返回 ALL_INTERVALS 的数据
    - 返回值为对应键的字符串或 JSON 值（按内容自动解码）
    - 复用统一响应封装与错误处理规范；无需 JWT
    """
    try:
        redis = get_async_redis_client()
        # 全周期读取
        if interval.lower() == "all":
            keys = [f"background:{exchange}:{symbol}:{itv}" for itv in ALL_INTERVALS]
            values = await redis.mget(keys)
            data: Dict[str, Any] = {}
            for itv, raw in zip(ALL_INTERVALS, values):
                data[itv] = _decode_value(raw)
            return success_response(data)

        # 单周期读取
        key = f"background:{exchange}:{symbol}:{interval}"
        raw = await redis.get(key)
        return success_response(_decode_value(raw))
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(code=StatusCode.SERVER_ERROR, message=f"读取背景数据失败: {e}")


@router.get("/dashboard/background/market_structure/{exchange}/{symbol}", response_model=BaseResponse[Any])
async def read_market_structure(exchange: str, symbol: str):
    """
    读取市场结构叙事：
    - 键：background:{exchange}:{symbol}:market_structure
    - 返回值为对应键的字符串或 JSON 值（自动解码）
    - 复用统一响应封装与错误处理；无需 JWT
    """
    try:
        redis = get_async_redis_client()
        key = f"background:{exchange}:{symbol}:market_structure"
        raw = await redis.get(key)
        return success_response(_decode_value(raw))
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(code=StatusCode.SERVER_ERROR, message=f"读取市场结构失败: {e}")
