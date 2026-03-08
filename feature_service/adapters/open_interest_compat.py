from __future__ import annotations

from typing import Any, Dict

from agent_server.agent_context.market_structure.open_interest.output import build_output
from feature_service.ports.open_interest_provider import OpenInterestProvider


class CompatOpenInterestProvider(OpenInterestProvider):
    async def get_open_interest(self, exchange: str, symbol: str) -> Dict[str, Any]:
        data = await build_output(exchange, symbol)
        return dict(data or {})
