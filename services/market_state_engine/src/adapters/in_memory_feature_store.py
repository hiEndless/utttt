from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from market_state_engine.ports.storage.feature_store import FeatureStore
from services.market_state_engine.src.engine import MarketStateFeatures


@dataclass
class _Entry:
    features: MarketStateFeatures
    stored_at_ms: int


class InMemoryFeatureStore(FeatureStore):
    """内存特征存储：用于开发/单机流程跑通。"""

    def __init__(self, *, ttl_ms: int = 15_000, max_items: int = 256) -> None:
        self._ttl_ms = int(ttl_ms)
        self._max_items = int(max_items)
        self._store: Dict[Tuple[str, str], _Entry] = {}

    def get(self, exchange: str, symbol: str) -> Optional[MarketStateFeatures]:
        key = (str(exchange), str(symbol))
        entry = self._store.get(key)
        if not entry:
            return None
        now = int(time.time() * 1000)
        if now - int(entry.stored_at_ms) > self._ttl_ms:
            self._store.pop(key, None)
            return None
        return entry.features

    def put(self, features: MarketStateFeatures) -> None:
        key = (str(features.exchange), str(features.symbol))
        now = int(time.time() * 1000)
        if len(self._store) >= self._max_items:
            oldest_key = min(self._store.items(), key=lambda kv: kv[1].stored_at_ms)[0]
            self._store.pop(oldest_key, None)
        self._store[key] = _Entry(features=features, stored_at_ms=now)
