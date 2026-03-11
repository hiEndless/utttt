from __future__ import annotations

from typing import Any, Dict


class NoopOrderbookProvider:
    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopOpenInterestProvider:
    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopHorizonsProvider:
    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopBehaviorProvider:
    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}


class NoopIndicatorsProvider:
    async def get_indicators(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {}
