from __future__ import annotations

from typing import Any, Dict, Protocol


class EventRecorder(Protocol):
    """事件记录端口：用于把关键中间结果写入审计存储（DB/Redis）。"""

    async def record_market_context(self, event_id: str, payload: Dict[str, Any]) -> None:
        """记录市场结构上下文（全量或摘要）。"""

    async def record_agent_output(self, event_id: str, agent_name: str, payload: Dict[str, Any]) -> None:
        """记录 agent 的结构化输出。"""

