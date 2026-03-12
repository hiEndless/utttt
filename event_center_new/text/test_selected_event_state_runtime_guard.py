from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.service import MarketStateService


def _sample_raw_market_structure() -> Dict[str, Any]:
    return {
        "horizons": {
            "fused": {
                "horizons": {
                    "short_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "medium"}}},
                    "mid_term": {
                        "market_background": {
                            "trend_memory": {"price_direction": "up", "price_strength": "strong"},
                            "trend_context": {"label": "trend_continuation"},
                            "volatility_state": "normal",
                        },
                        "participant_background": {"crowding": "normal", "stability": "stable"},
                    },
                    "long_term": {"market_background": {"trend_memory": {"price_direction": "down", "price_strength": "medium"}}},
                }
            }
        },
        "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
    }


class _RawStructureProvider:
    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        _ = (exchange, symbol)
        return _sample_raw_market_structure()


class _SelectedEventProvider:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        _ = (exchange, symbol, limit)
        return [
            {
                "asset": "binance:ETHUSDT",
                "ts_ms": 1710000000000,
                "selected_type": "breakout_signal",
                "direction_hint": "bullish",
                "priority": "high",
                "context_snapshot": {"reason": "runtime-guard"},
                "route": {"horizon": "5m"},
            }
        ]


def test_selected_event_runtime_guard_for_market_state_evidence():
    async def _run() -> Dict[str, Any]:
        svc = MarketStateService(
            raw_structure_provider=_RawStructureProvider(),
            selected_event_provider=_SelectedEventProvider(),
        )
        return await svc.get_market_state("binance", "ETHUSDT")

    out = asyncio.run(_run())
    assert out.get("status") == "ok"
    evidence = dict((out.get("state_features") or {}).get("evidence") or {})
    assert evidence.get("selected_events_count") == 1
    assert evidence.get("selected_event_types") == ["breakout_signal"]
    assert evidence.get("selected_event_directions") == ["bullish"]
    assert evidence.get("selected_event_priorities") == ["high"]
    preview = list(evidence.get("selected_events_preview") or [])
    assert preview and isinstance(preview[0], dict)
    assert dict(preview[0]).get("route") == {"horizon": "5m"}
    assert "selected_event_context_attached" in list(out.get("anomaly_flags") or [])
