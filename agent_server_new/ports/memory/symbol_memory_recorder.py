from __future__ import annotations

from typing import Any, Dict, Protocol


class SymbolMemoryRecorder(Protocol):
    """Symbol 级市场记忆写入端口（仅记录市场背景与决策，不记录仓位明细）。"""

    async def record_symbol_memory(self, exchange: str, symbol: str, payload: Dict[str, Any]) -> None:
        ...
