from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


class StaticOrderbookProvider:
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class StaticOpenInterestProvider:
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class StaticHorizonsProvider:
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)


class StaticBehaviorProvider:
    def __init__(self, payload: Dict[str, Any] | None = None) -> None:
        self._payload = dict(payload or {})

    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return deepcopy(self._payload)
