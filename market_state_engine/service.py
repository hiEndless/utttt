from __future__ import annotations

from typing import Any, Dict

from market_state_engine.engine import MarketStateEngine
from market_state_engine.ports.raw_structure_provider import RawStructureProvider


class MarketStateService:
    """状态层用例服务：聚合 raw structure 并产出状态快照。"""

    def __init__(self, raw_structure_provider: RawStructureProvider) -> None:
        self._raw_structure_provider = raw_structure_provider
        self._engine = MarketStateEngine()

    async def get_market_state(self, exchange: str, symbol: str) -> Dict[str, Any]:
        raw_market_structure = await self._raw_structure_provider.get_raw_structure(exchange=exchange, symbol=symbol)
        if not isinstance(raw_market_structure, dict):
            raise TypeError("invalid_market_structure")

        msl, features = self._engine.build(exchange=exchange, symbol=symbol, market_structure=raw_market_structure)
        anomaly_flags = [str(x) for x in list(features.anomalies.get("flags") or []) if x]

        return {
            "exchange": exchange,
            "symbol": symbol,
            "msl": msl.to_llm_dict(),
            "state_features": features.to_dict(),
            "anomaly_flags": anomaly_flags,
            "raw_market_structure": raw_market_structure,
        }
