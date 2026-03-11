from __future__ import annotations

from typing import Any, Dict, Protocol


class BehaviorProvider(Protocol):
    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
