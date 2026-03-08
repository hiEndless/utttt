from __future__ import annotations

from typing import Any, Dict, Protocol


class HorizonsProvider(Protocol):
    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
