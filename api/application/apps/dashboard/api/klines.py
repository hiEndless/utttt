from __future__ import annotations

import json
from typing import Any, List, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, StatusCode, BusinessException, success_response

# 路由（无需用户 JWT 验证）
router = APIRouter(tags=["Dashboard - Klines"])


class KlineItem(BaseModel):
    """标准化后的 K 线数据结构"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def _parse_binance_klines(payload: Any) -> List[Dict[str, Any]]:
    """
    将币安 K 线数据转换为标准 OHLCV 格式：
    - 支持数组格式：[openTime, "o","h","l","c","v", closeTime, ...]
    - 支持字典格式：{"t": openTime, "o": "o", "h": "h", "l": "l", "c": "c", "v": "v"}
    """
    result: List[Dict[str, Any]] = []
    if not payload:
        return result

    # 若为字典，可能含数据字段
    if isinstance(payload, dict):
        if "klines" in payload and isinstance(payload["klines"], list):
            payload = payload["klines"]
        elif "data" in payload and isinstance(payload["data"], list):
            payload = payload["data"]
        else:
            payload = [payload]

    # 解析列表
    for item in payload:
        if isinstance(item, dict):
            t = item.get("t") or item.get("timestamp")
            o = item.get("o") or item.get("open")
            h = item.get("h") or item.get("high")
            l = item.get("l") or item.get("low")
            c = item.get("c") or item.get("close")
            v = item.get("v") or item.get("volume")
            if t is None or o is None or h is None or l is None or c is None or v is None:
                continue
            try:
                result.append({
                    "timestamp": int(t),
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                })
            except Exception:
                continue
        elif isinstance(item, (list, tuple)) and len(item) >= 6:
            # 币安数组格式：索引约定
            try:
                open_time = int(item[0])
                o = float(item[1])
                h = float(item[2])
                l = float(item[3])
                c = float(item[4])
                v = float(item[5])
                result.append({
                    "timestamp": open_time,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                })
            except Exception:
                continue
        else:
            # 不支持的元素，跳过
            continue
    return result


@router.get("/dashboard/klines/{exchange}/{symbol}/{interval}", response_model=BaseResponse[List[KlineItem]])
async def read_klines(exchange: str, symbol: str, interval: str):
    """
    从 Redis 读取指定交易所/币种/周期的 K 线，并标准化返回
    - 键名：klines:{exchange}:{symbol}:{interval}
    - 无需用户 JWT 验证
    - 统一响应封装与错误处理
    """
    redis = get_async_redis_client()
    key = f"klines:{exchange}:{symbol}:{interval}"

    try:
        raw = await redis.get(key)
        if not raw:
            return success_response([])
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            # 若为非 JSON（不符合约定），视为无数据
            return success_response([])

        # 币安数据标准化（其他交易所若结构兼容也能解析）
        items = _parse_binance_klines(payload)
        return success_response([KlineItem(**it) for it in items])
    except BusinessException:
        raise
    except Exception as e:
        raise BusinessException(code=StatusCode.SERVER_ERROR, message=f"读取 K 线失败: {e}")

