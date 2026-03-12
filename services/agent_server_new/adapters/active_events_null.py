from __future__ import annotations

from typing import Any, Dict, List

from services.agent_server_new.ports.data.active_events_provider import ActiveEventsProvider


class NullActiveEventsProvider(ActiveEventsProvider):
    """空事件 provider：当上游不可用时返回空集合，避免注入 stub 语义。"""

    async def get_active_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        _ = (exchange, symbol)
        return []

