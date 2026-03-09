from __future__ import annotations

import datetime
import time
from typing import Any, Dict

from market_state_engine.engine import MarketStateEngine
from market_state_engine.errors import FeatureDataUnavailableFromUpstreamError
from market_state_engine.ports.raw_structure_provider import RawStructureProvider


class MarketStateService:
    """状态层用例服务：聚合 raw structure 并产出状态快照。"""

    def __init__(self, raw_structure_provider: RawStructureProvider) -> None:
        self._raw_structure_provider = raw_structure_provider
        self._engine = MarketStateEngine()

    @staticmethod
    def _build_data_unavailable_payload(exchange: str, symbol: str, degraded_reasons: list[str]) -> Dict[str, Any]:
        now_ms = int(time.time() * 1000)
        ts_iso = (
            datetime.datetime.fromtimestamp(float(now_ms) / 1000.0, tz=datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        return {
            "exchange": exchange,
            "symbol": symbol,
            "status": "data_unavailable",
            "reason_code": "feature_data_unavailable",
            "degraded_reasons": [str(x) for x in list(degraded_reasons or []) if x],
            "msl": {
                "version": 1,
                "timestamp": ts_iso,
                "symbol": symbol,
                "market_regime": {
                    "trend": "unknown",
                    "phase": "unknown",
                    "timeframe_alignment": "unknown",
                    "strength": 0.0,
                },
                "liquidity_state": {
                    "dominant_pressure": "unknown",
                    "liquidity_risk": "unknown",
                    "orderbook_bias": "unknown",
                    "liquidation_proximity": "unknown",
                },
                "positioning_state": {
                    "crowding": "unknown",
                    "whale_bias": "unknown",
                    "retail_bias": "unknown",
                    "oi_trend": "unknown",
                },
                "volatility_state": {
                    "volatility_regime": "unknown",
                    "expansion_risk": "unknown",
                    "volatility_direction": "unknown",
                },
                "sentiment_state": {
                    "funding_sentiment": "unknown",
                    "social_sentiment": "unknown",
                    "news_bias": "unknown",
                    "overall_sentiment": "unknown",
                },
                "risk_state": {
                    "cascade_risk": "unknown",
                    "squeeze_probability": "unknown",
                    "reversal_risk": "unknown",
                },
                "market_structure_state": {
                    "support_strength": "unknown",
                    "resistance_strength": "unknown",
                    "range_state": "unknown",
                    "trend_structure": "unknown",
                },
                "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
                "anomalies": ["data_unavailable"],
                "summary": "上游 feature_service 关键结构数据不可用，状态推断已短路",
            },
            "state_features": {
                "exchange": exchange,
                "symbol": symbol,
                "ts": now_ms,
                "status": "data_unavailable",
                "horizons": {},
                "orderbook": {},
                "open_interest": {},
                "anomalies": {"flags": ["data_unavailable"]},
                "evidence": {"message": "上游 feature_service 关键结构数据不可用"},
                "derived": {},
            },
            "anomaly_flags": ["data_unavailable"],
            "raw_market_structure": {},
        }

    async def get_market_state(self, exchange: str, symbol: str) -> Dict[str, Any]:
        try:
            raw_market_structure = await self._raw_structure_provider.get_raw_structure(exchange=exchange, symbol=symbol)
        except FeatureDataUnavailableFromUpstreamError as exc:
            return self._build_data_unavailable_payload(
                exchange=exc.exchange,
                symbol=exc.symbol,
                degraded_reasons=exc.degraded_reasons,
            )
        if not isinstance(raw_market_structure, dict):
            raise TypeError("invalid_market_structure")

        msl, features = self._engine.build(exchange=exchange, symbol=symbol, market_structure=raw_market_structure)
        anomaly_flags = [str(x) for x in list(features.anomalies.get("flags") or []) if x]

        return {
            "exchange": exchange,
            "symbol": symbol,
            "status": "ok",
            "msl": msl.to_llm_dict(),
            "state_features": features.to_dict(),
            "anomaly_flags": anomaly_flags,
            "raw_market_structure": raw_market_structure,
        }
