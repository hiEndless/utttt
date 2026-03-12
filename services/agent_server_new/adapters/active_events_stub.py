from __future__ import annotations

from typing import Any, Dict, List

from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider


class StubActiveEventsProvider(ActiveEventsProvider):
    """占位实现：用于未接入事件中心前跑通流程。"""

    async def get_active_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        return []

