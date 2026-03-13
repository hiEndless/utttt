import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.ports.market_state import MarketStateSnapshot


def _sample_msl() -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": "ETHUSDT",
        "market_regime": {"trend": "bullish", "phase": "continuation", "timeframe_alignment": "aligned", "strength": 0.72},
        "liquidity_state": {"dominant_pressure": "buyers", "liquidity_risk": "neutral", "orderbook_bias": "neutral", "liquidation_proximity": "none"},
        "positioning_state": {"crowding": "balanced", "whale_bias": "unknown", "retail_bias": "unknown", "oi_trend": "expanding"},
        "volatility_state": {"volatility_regime": "normal", "expansion_risk": "unknown", "volatility_direction": "upside"},
        "market_risk_state": {"cascade_risk": "low", "squeeze_probability": "low", "reversal_risk": "low"},
        "market_structure_state": {"support_strength": "unknown", "resistance_strength": "unknown", "range_state": "breakout", "trend_structure": "hh_hl"},
        "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
        "anomalies": [],
        "summary": "ok",
    }


class _MarketState:
    async def get_market_state(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return MarketStateSnapshot(
            exchange="binance",
            symbol="ETHUSDT",
            msl=_build_msl_from_dict(_sample_msl()),
            msl_meta={"schema_version": 2, "inference_version": "msl_generator_v2"},
            cross_horizon={"alignment": "aligned", "suggested_policy": "follow_long_term", "policy_reason": "timeframe_aligned"},
            state_features={"evidence": {}, "anomalies": {}},
        )


class _Position:
    async def get_position_context(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {
            "current_position": {"cooldown_seconds_left": 20},
            "portfolio_risk": {"risk_state": "warn"},
        }


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return [{"type": "volatility_spike", "score": 0.8}]


class _Recorder:
    def __init__(self) -> None:
        self.outputs: List[Tuple[str, str, Dict[str, Any]]] = []

    async def record_market_context(self, event_id: str, payload: Dict[str, Any]) -> None:
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload: Dict[str, Any]) -> None:
        self.outputs.append((event_id, agent_name, dict(payload or {})))


def test_decision_trace_removes_legacy_semantic_snapshot_fields() -> None:
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            recorder=recorder,
        )
        await wf.run_with_result(
            TradeEventInput(
                event_id="evt-risk-trace-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )

        trace_payload = {}
        for _, name, payload in recorder.outputs:
            if name == "decision_trace":
                trace_payload = payload
                break
        assert trace_payload
        assert "intent" not in trace_payload
        assert "rule_plan" not in trace_payload
        assert "strategy_gate_result" not in trace_payload
        assert "risk_gate" not in trace_payload

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
