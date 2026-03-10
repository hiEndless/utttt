from __future__ import annotations

from typing import Any, Dict, List, Protocol


class SelectedEventProvider(Protocol):
    """selected_event 提供端口：状态层通过该抽象读取结构事件。"""

    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        """返回指定交易对的 selected_event 列表（新到旧）。"""
