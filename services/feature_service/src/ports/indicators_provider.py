from __future__ import annotations

from typing import Any, Dict, Protocol


class IndicatorsProvider(Protocol):
    async def get_indicators(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
