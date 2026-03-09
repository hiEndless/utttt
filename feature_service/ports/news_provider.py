from __future__ import annotations

from typing import Any, Dict, Protocol


class NewsProvider(Protocol):
    async def get_news_features(self, exchange: str, symbol: str) -> Dict[str, Any]:
        ...
