from __future__ import annotations

import json
from typing import Any, Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..account.views import get_current_user_id
from ..settings.models import ExchangeAccount
from ...common.redis_client import get_async_redis_client
from ...common.status_codes import StatusCode, BaseResponse, BusinessException, success_response

app = APIRouter()


class PositionItem(BaseModel):
    """仓位信息模型"""
    symbol: str
    position_side: str
    size: str
    notional: str
    pnl_ratio: str
    open_time: str
    trade_id: str
    initialMargin: str
    leverage: str


class PositionResponse(BaseModel):
    """仓位响应模型"""
    positions: List[PositionItem]
    exchange: str


async def _read_json_list(client, key: str) -> list:
    """从Redis读取JSON列表数据"""
    try:
        v = await client.get(key)
        if not v:
            return []
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回空列表
            return []
    except Exception:
        return []


@app.get("/dashboard/positions", response_model=BaseResponse[List[PositionResponse]])
async def get_user_positions(
    symbol: Optional[str] = Query(None, description="可选的交易对符号，如 ETHUSDT"),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取当前用户所有活跃交易所账户的仓位信息
    
    根据用户ID查询所有is_active=True的交易所账户，
    从Redis中读取对应交易所的仓位数据并返回
    """
    # 查询用户所有活跃的交易所账户
    active_accounts = await ExchangeAccount.filter(
        user_id=user_id, 
        is_active=True, 
        is_deleted=False
    ).order_by("exchange")
    
    if not active_accounts:
        # 如果没有活跃的交易所账户，返回空列表
        return success_response([])
    
    redis_client = get_async_redis_client()
    results: List[PositionResponse] = []
    
    for account in active_accounts:
        exchange = account.exchange
        key = f"positions:{exchange}"
        
        # 从Redis读取仓位数据
        data = await _read_json_list(redis_client, key)
        
        if not data:
            continue
            
        # 过滤指定symbol的仓位（如果提供了symbol参数）
        filtered_positions = []
        for p in data:
            if isinstance(p, dict):
                pos_symbol = str(p.get("symbol", ""))
                if symbol is None or pos_symbol == symbol:
                    filtered_positions.append(PositionItem(
                        symbol=pos_symbol,
                        position_side=str(p.get("positionSide", "")),
                        size=str(p.get("positionAmt", "")),
                        notional=str(p.get("notional", "")),
                        pnl_ratio=str(p.get("pnl_ratio", "")),
                        open_time=str(p.get("open_time", "")),
                        trade_id=str(p.get("trade_id", "")),
                        initialMargin=str(p.get("initialMargin", "")),
                        leverage=str(p.get("leverage", ""))
                    ))
        
        if filtered_positions:
            results.append(PositionResponse(
                positions=filtered_positions,
                exchange=exchange
            ))
    
    return success_response(results)


@app.get("/dashboard/positions/{exchange}", response_model=BaseResponse[PositionResponse])
async def get_exchange_positions(
    exchange: str,
    symbol: Optional[str] = Query(None, description="可选的交易对符号，如 ETHUSDT"),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取指定交易所的仓位信息
    
    验证用户是否有权限访问该交易所的仓位数据
    """
    # 验证用户是否绑定了该交易所且账户处于活跃状态
    account = await ExchangeAccount.get_or_none(
        user_id=user_id,
        exchange=exchange,
        is_active=True,
        is_deleted=False
    )
    
    if not account:
        raise BusinessException(code=StatusCode.NOT_FOUND, message=f"Exchange account {exchange} not found or not active")
    
    redis_client = get_async_redis_client()
    key = f"positions:{exchange}"
    
    # 从Redis读取仓位数据
    data = await _read_json_list(redis_client, key)
    
    positions: List[PositionItem] = []
    if data:
        for p in data:
            if isinstance(p, dict):
                pos_symbol = str(p.get("symbol", ""))
                if symbol is None or pos_symbol == symbol:
                    positions.append(PositionItem(
                        symbol=pos_symbol,
                        position_side=str(p.get("positionSide", "")),
                        size=str(p.get("positionAmt", "")),
                        notional=str(p.get("notional", "")),
                        pnl_ratio=str(p.get("pnl_ratio", "")),
                        open_time=str(p.get("open_time", "")),
                        trade_id=str(p.get("trade_id", "")),
                        initialMargin=str(p.get("initialMargin", "")),
                        leverage=str(p.get("leverage", ""))
                    ))
    
    return success_response(PositionResponse(
        positions=positions,
        exchange=exchange
    ))