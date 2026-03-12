from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

from services.market_state_engine.src.contracts import MarketStateMSL


@dataclass(frozen=True)
class MarketStateSnapshot:
    """状态层输出：供决策层消费的稳定状态快照。"""

    exchange: str
    symbol: str
    msl: MarketStateMSL
    msl_meta: Dict[str, Any] = field(default_factory=dict)
    msl_bundle: Dict[str, Any] = field(default_factory=dict)
    msl_bundle_meta: Dict[str, Any] = field(default_factory=dict)
    cross_horizon: Dict[str, Any] = field(default_factory=dict)
    state_features: Dict[str, Any] = field(default_factory=dict)
    anomaly_flags: List[str] = field(default_factory=list)
    raw_market_structure: Dict[str, Any] = field(default_factory=dict)


class MarketStateProvider(Protocol):
    """市场状态端口：决策层只能通过该抽象读取状态层产物。"""

    async def get_market_state(self, exchange: str, symbol: str) -> MarketStateSnapshot:
        """返回状态层快照，包含 MSL、关键状态特征和审计用原始结构。"""
