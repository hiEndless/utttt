from __future__ import annotations

from typing import Any, Dict

from agent_server.agent_context.market_structure.behavioral.behavior_output import build_behavior_output
from feature_service.ports.behavior_provider import BehaviorProvider


class CompatBehaviorProvider(BehaviorProvider):
    async def get_behavior(self, exchange: str, symbol: str) -> Dict[str, Any]:
        data = await build_behavior_output(exchange, symbol)
        return dict(data or {})
