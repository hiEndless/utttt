from __future__ import annotations

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...account.views import get_current_user_id
from ...settings.models import ExchangeAccount
from ....common.redis_client import get_async_redis_client
from ....common.status_codes import BaseResponse, success_response

# 创建带有标签的路由
router = APIRouter(tags=["Dashboard - Account Balance"])

class BalanceItem(BaseModel):
    """账户余额信息模型"""
    asset: str
    free: str
    locked: str
    total: str


class BalanceResponse(BaseModel):
    """余额响应模型"""
    balances: List[BalanceItem]
    exchange: str


@router.get("/dashboard/balances", response_model=BaseResponse[List[BalanceResponse]])
async def get_user_balances(
    asset: Optional[str] = Query(None, description="可选的资产符号，如 BTC"),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取当前用户所有活跃交易所账户的余额信息
    
    根据用户ID查询所有is_active=True的交易所账户，
    从Redis中读取对应交易所的余额数据并返回
    """
    # 查询用户所有活跃的交易所账户
    active_accounts = await ExchangeAccount.filter(
        user_id=user_id, 
        is_active=True, 
        is_deleted=False
    ).order_by("exchange")
    
    if not active_accounts:
        return success_response([])
    
    redis_client = get_async_redis_client()
    results: List[BalanceResponse] = []
    
    for account in active_accounts:
        exchange = account.exchange
        key = f"balances:{exchange}"
        
        # 从Redis读取余额数据（这里只是示例，实际实现需要根据您的数据结构）
        # data = await _read_json_list(redis_client, key)
        # ... 处理逻辑
        
        # 示例返回
        results.append(BalanceResponse(
            balances=[],
            exchange=exchange
        ))
    
    return success_response(results)


@router.get("/dashboard/balances/{exchange}", response_model=BaseResponse[BalanceResponse])
async def get_exchange_balances(
    exchange: str,
    asset: Optional[str] = Query(None, description="可选的资产符号，如 BTC"),
    user_id: str = Depends(get_current_user_id)
):
    """
    获取指定交易所的余额信息
    
    验证用户是否有权限访问该交易所的余额数据
    """
    # 验证用户是否绑定了该交易所且账户处于活跃状态
    account = await ExchangeAccount.get_or_none(
        user_id=user_id,
        exchange=exchange,
        is_active=True,
        is_deleted=False
    )
    
    if not account:
        # 这里应该抛出异常，但为了示例简化处理
        return success_response(BalanceResponse(balances=[], exchange=exchange))
    
    # 示例返回
    return success_response(BalanceResponse(
        balances=[],
        exchange=exchange
    ))