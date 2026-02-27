"""
Settings 应用模块初始化
提供统一的路由注册接口
"""

from fastapi import APIRouter

# 导入各个功能模块的路由
from .api.exchange_accounts import router as exchange_accounts_router
from .api.model_providers import router as model_providers_router
from .api.agent_model_configs import router as agent_model_configs_router
from .api.notification_channels import router as notification_channels_router

# 创建主路由
app = APIRouter()

# 注册所有子路由
app.include_router(exchange_accounts_router)
app.include_router(model_providers_router)
app.include_router(agent_model_configs_router)
app.include_router(notification_channels_router)

# 如果有其他功能模块，可以在这里继续添加
# app.include_router(other_router)