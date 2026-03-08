from __future__ import annotations

from typing import Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from market_state_engine.engine import MarketStateFeatures


class FeatureStore(Protocol):
    """特征存储端口：用于复用已计算的特征，避免重复聚合。"""

    def get(self, exchange: str, symbol: str) -> Optional["MarketStateFeatures"]:
        ...

    def put(self, features: "MarketStateFeatures") -> None:
        ...
