from __future__ import annotations

from typing import Any, Dict, List, Protocol


class PositionProvider(Protocol):
    """仓位端口：屏蔽交易所 API 细节与数据形态差异。"""

    async def get_positions(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        """返回当前持仓列表（可包含多 trade_id / 多 side）。"""

