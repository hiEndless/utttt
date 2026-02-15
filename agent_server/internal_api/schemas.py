from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RefreshKlineRequest(BaseModel):
    exchange: str = Field(default="binance")
    symbol: str
    intervals: Optional[List[str]] = None
    max_concurrency: int = Field(default=2, ge=1, le=6)


class RefreshMarketStateRequest(BaseModel):
    exchange: str = Field(default="binance")
    symbol: str


class BuildContextRequest(BaseModel):
    agent: str
    exchange: str = Field(default="binance")
    symbol: str
    horizon: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    # 中文注释：保持 payload 自由结构，便于直接透传 final_signal（或其他工作流输入）。
    payload: Dict[str, Any]

