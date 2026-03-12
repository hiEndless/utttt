from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class ExecutionStateRepository(Protocol):
    """执行状态存储端口：用于读取/写入风控与执行状态（通常在 Redis）。"""

    async def get_execution_state(self, exchange: str, symbol: str, trade_id: str) -> Optional[Dict[str, Any]]:
        """读取某笔交易（或某个仓位）的执行状态。"""

    async def save_execution_state(self, exchange: str, symbol: str, trade_id: str, state: Dict[str, Any]) -> None:
        """写入某笔交易（或某个仓位）的执行状态。"""

