from __future__ import annotations

from typing import Any, Dict, Protocol


class OrderbookProvider(Protocol):
    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
