"""
Dashboard 应用模块初始化
提供统一的路由注册接口
"""

from fastapi import APIRouter

# 导入各个功能模块的路由
from .api.positions import router as positions_router
from .api.account_balance import router as account_balance_router

# 创建主路由
app = APIRouter()

# 注册所有子路由
app.include_router(positions_router)
app.include_router(account_balance_router)

# 如果有其他功能模块，可以在这里继续添加
# app.include_router(other_router)