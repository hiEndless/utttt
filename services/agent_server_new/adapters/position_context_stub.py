from __future__ import annotations

from typing import Any, Dict

from agent_server_new.ports.data.position_context_provider import PositionContextProvider


class StubPositionContextProvider(PositionContextProvider):
    """占位实现：用于在未接入真实仓位/账户系统前跑通流程。"""

    async def get_position_context(self, exchange: str, symbol: str) -> Dict[str, Any]:
        return {
            "exchange": exchange,
            "symbol": symbol,
            "has_position": False,
            "current_position": None,
            "avg_entry": None,
            "exposure": None,
            "margin": None,
            "portfolio_risk": None,
        }

