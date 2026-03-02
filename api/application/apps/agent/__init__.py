"""
Agent 应用模块初始化
提供 Agent 运行态状态与开关控制接口
"""

from fastapi import APIRouter

from .api.status import router as status_router
from .api.toggle import router as toggle_router

app = APIRouter()
app.include_router(status_router)
app.include_router(toggle_router)

