from __future__ import annotations

from typing import Any, Dict

from feature_service.ports.behavior_provider import BehaviorProvider
from feature_service.ports.horizons_provider import HorizonsProvider
from feature_service.ports.open_interest_provider import OpenInterestProvider
from feature_service.ports.orderbook_provider import OrderbookProvider


class MigratedOrderbookProvider(OrderbookProvider):
    """Migration provider using legacy market_structure orderbook output."""

    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        from feature_service.providers.market_structure_migrated.orderbook.output import build_output

        data = await build_output(exchange, symbol)
        return dict(data or {})


class MigratedOpenInterestProvider(OpenInterestProvider):
    """Migration provider using legacy market_structure open_interest output."""

    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        from feature_service.providers.market_structure_migrated.open_interest.output import build_output

        data = await build_output(exchange, symbol)
        return dict(data or {})


class MigratedHorizonsProvider(HorizonsProvider):
    """Migration provider using legacy market_structure horizons output."""

    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        from feature_service.providers.market_structure_migrated.horizons.output import build_output

        data = await build_output(exchange, symbol)
        return dict(data or {})


class MigratedBehaviorProvider(BehaviorProvider):
    """Migration provider using legacy market_structure behavioral output."""

    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        from feature_service.providers.market_structure_migrated.behavioral.behavior_output import build_behavior_output

        data = await build_behavior_output(exchange, symbol)
        return dict(data or {})
