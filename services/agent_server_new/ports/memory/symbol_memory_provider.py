from __future__ import annotations

from typing import Any, Dict, Protocol


class SymbolMemoryProvider(Protocol):
    """Symbol 级市场记忆读取端口（仅用于 agent 决策背景）。"""

    async def get_symbol_memory(self, exchange: str, symbol: str, limit: int = 20) -> Dict[str, Any]:
        ...
