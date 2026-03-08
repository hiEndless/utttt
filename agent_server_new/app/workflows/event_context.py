from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from market_state_engine.contracts import MarketStateMSL


@dataclass(frozen=True)
class EventContext:
    """工作流统一上下文：用于避免参数爆炸，并支持回放（replay）。"""

    event_id: str
    exchange: str
    symbol: str
    timestamp_ms: int

    signal_event: Dict[str, Any]
    msl: MarketStateMSL
    key_market_features: Dict[str, Any]
    active_events: List[Dict[str, Any]]
    position_context: Dict[str, Any]

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
