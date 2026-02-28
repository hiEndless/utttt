from __future__ import annotations

from typing import Any, Optional, List, Dict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...account.views import get_current_user_id
from ..models import TradeEvent, Trade
from ....common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

# 路由
router = APIRouter(tags=["Dashboard - Trade Events"])


class TradeEventItem(BaseModel):
    """事件信息模型（便于响应序列化）"""
    event_id: str
    event_type: str
    event_at: int
    symbol: Optional[str] = None
    exchange: Optional[str] = None
    direction: str
    mark_price: Optional[str] = None
    market_context: Optional[Dict[str, Any]] = None
    market_structure: Optional[Dict[str, Any]] = None
    event_data: Dict[str, Any]
    indicators_snapshot: Optional[Dict[str, Any]] = None
    is_verified: bool
    verification_at: Optional[int] = None
    verification_mark_price: Optional[str] = None
    event_importance: int
    event_summary: Optional[str] = None


ALLOWED_KEYS: set[str] = {
    "event_id",
    "event_type",
    "event_at",
    "symbol",
    "exchange",
    "direction",
    "mark_price",
    "market_context",
    "market_structure",
    "event_data",
    "indicators_snapshot",
    "is_verified",
    "verification_at",
    "verification_mark_price",
    "event_importance",
    "event_summary",
}


def _to_item(e: TradeEvent) -> TradeEventItem:
    """将 ORM 对象转换为响应模型"""
    return TradeEventItem(
        event_id=str(e.event_id),
        event_type=str(e.event_type),
        event_at=int(e.event_at),
        symbol=str(e.symbol) if e.symbol is not None else None,
        exchange=str(e.exchange) if e.exchange is not None else None,
        direction=str(e.direction),
        mark_price=str(e.mark_price) if e.mark_price is not None else None,
        market_context=e.market_context if e.market_context is not None else None,
        market_structure=e.market_structure if e.market_structure is not None else None,
        event_data=e.event_data,
        indicators_snapshot=e.indicators_snapshot if e.indicators_snapshot is not None else None,
        is_verified=bool(e.is_verified),
        verification_at=int(e.verification_at) if e.verification_at is not None else None,
        verification_mark_price=str(e.verification_mark_price) if e.verification_mark_price is not None else None,
        event_importance=int(e.event_importance),
        event_summary=str(e.event_summary) if e.event_summary is not None else None,
    )


@router.get("/dashboard/trades/{trade_id}/events", response_model=BaseResponse[Any])
async def get_trade_events(
    trade_id: str,
    key: Optional[str] = Query(None, description="可选：只返回指定键的值"),
    since: Optional[int] = Query(None, description="可选：开始时间戳(ms)，过滤事件"),
    until: Optional[int] = Query(None, description="可选：结束时间戳(ms)，过滤事件"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量上限"),
    user_id: str = Depends(get_current_user_id),
):
    """
    读取指定持仓（按 trade_id）的事件信息
    - 复用认证中间件，通过当前用户鉴权
    - 支持按时间范围与数量限制过滤
    - 支持 key 参数仅返回某个字段的字符串或 JSON 值
    """
    # 校验该 trade 是否属于当前用户
    print(trade_id, user_id)
    trade = await Trade.get_or_none(trade=trade_id, user_id=user_id)
    if not trade:
        raise BusinessException(code=StatusCode.NOT_FOUND, message=f"trade {trade_id} 不存在或无权限访问")

    # 查询事件
    q = TradeEvent.filter(trade__trade=trade_id)
    if since is not None:
        q = q.filter(event_at__gte=since)
    if until is not None:
        q = q.filter(event_at__lte=until)
    events: List[TradeEvent] = await q.order_by("event_at").limit(limit)

    if key:
        if key not in ALLOWED_KEYS:
            raise BusinessException(code=StatusCode.PARAM_ERROR, message=f"不支持的键：{key}")
        # 返回指定键的值列表（字符串或 JSON）
        values: List[Any] = []
        for e in events:
            v = getattr(e, key, None)
            # 统一将 Decimal 转字符串，避免前端解析差异
            if v is None:
                values.append(None)
            elif isinstance(v, (int, bool, dict, list)):
                values.append(v)
            else:
                values.append(str(v))
        return success_response(values)

    # 默认返回标准化后的事件列表
    items = [_to_item(e) for e in events]
    return success_response(items)

