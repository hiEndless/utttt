from __future__ import annotations

from typing import Any, Dict

from agent_server.agent_context.market_structure.orderbook.output import build_output
from feature_service.ports.orderbook_provider import OrderbookProvider


class CompatOrderbookProvider(OrderbookProvider):
    async def get_orderbook(self, exchange: str, symbol: str) -> Dict[str, Any]:
        data = await build_output(exchange, symbol)
        return dict(data or {})
