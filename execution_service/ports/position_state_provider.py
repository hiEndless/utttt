from __future__ import annotations

from typing import Any, Dict, Protocol


class PositionStateProvider(Protocol):
    """仓位状态端口：提供当前仓位、敞口、PnL 等执行前约束。"""

    async def get_position_state(
        self,
        exchange: str,
        symbol: str,
        account_id: str = "main",
    ) -> Dict[str, Any]:
        ...
