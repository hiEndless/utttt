from __future__ import annotations

from typing import Any, Dict, Protocol


class SocialProvider(Protocol):
    async def get_social_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
