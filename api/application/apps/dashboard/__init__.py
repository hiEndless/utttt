"""
Dashboard 应用模块初始化
提供统一的路由注册接口
"""

from fastapi import APIRouter

# 导入各个功能模块的路由
from .api.positions import router as positions_router
from .api.account_balance import router as account_balance_router
from .api.force_stream import router as force_stream_router
from .api.l1_stream import router as l1_stream_router
from .api.trade_events import router as trade_events_router
from .api.klines import router as klines_router

# 创建主路由
app = APIRouter()

# 注册所有子路由
app.include_router(positions_router)
app.include_router(account_balance_router)
app.include_router(force_stream_router)
app.include_router(l1_stream_router)
app.include_router(trade_events_router)
app.include_router(klines_router)

# 如果有其他功能模块，可以在这里继续添加
# app.include_router(other_router)
