from __future__ import annotations

from typing import Any, Dict

from agent_server.agent_context.market_structure.horizons.output import build_output
from feature_service.ports.horizons_provider import HorizonsProvider


class CompatHorizonsProvider(HorizonsProvider):
    async def get_horizons(self, exchange: str, symbol: str) -> Dict[str, Any]:
        data = await build_output(exchange, symbol)
        return dict(data or {})
