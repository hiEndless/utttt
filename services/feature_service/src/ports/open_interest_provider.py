from __future__ import annotations

from typing import Any, Dict, Protocol


class OpenInterestProvider(Protocol):
    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
