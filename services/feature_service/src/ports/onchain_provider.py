from __future__ import annotations

from typing import Any, Dict, Protocol


class OnchainProvider(Protocol):
    async def get_onchain_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
