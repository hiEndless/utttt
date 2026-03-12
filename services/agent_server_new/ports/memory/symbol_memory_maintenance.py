from __future__ import annotations

from typing import Any, Dict, List, Protocol


class SymbolMemoryMaintenance(Protocol):
    """Symbol 记忆维护端口：用于后台 summary 整理任务。"""

    async def list_symbols(self, limit: int = 1000) -> List[Dict[str, str]]:
        ...

    async def rebuild_symbol_summary(self, exchange: str, symbol: str, *, window: int = 50) -> Dict[str, Any]:
        ...
