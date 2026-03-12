import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.adapters.symbol_memory_inmemory import InMemorySymbolMemoryAdapter
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import ActionIntent, Confidence, ExecutionPlan, RiskAllowance, RulePlan, SignalVerdict
from services.agent_server_new.domain.strategy_gate import StrategyGateResult
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
            msl_meta={"schema_version": 2},
            cross_horizon={"suggested_policy": "follow_long_term"},
            state_features={
                "evidence": {
                    "alternative_sources_fusion": {
                        "preferred_source": "feature",
                        "conflicts": [{"source": "news", "feature_state": "primary", "event_state": "event_evidence_present"}],
                        "merged": {
                            "available_sources": ["news"],
                            "unavailable_sources": ["social", "onchain"],
                            "by_source": {
                                "news": {"provider_state": "primary", "feature_keys": ["headline_score"]},
                                "social": {"provider_state": "empty", "feature_keys": []},
                                "onchain": {"provider_state": "empty", "feature_keys": []},
                            },
                        },
                    }
                },
                "anomalies": {},
            },
            anomaly_flags=[
                "state_features_semantic_contract_missing",
                "msl_meta_schema_version_missing",
                "state_features_alternative_source_provider_state_invalid",
                "external_event_input_ignored",
            ],
        )


class _Position:
    async def get_position_context(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {"has_position": False}


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return []


class _Recorder:
    def __init__(self) -> None:
        self.outputs = []

    async def record_market_context(self, event_id: str, payload):  # noqa: ANN001
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload):  # noqa: ANN001
        self.outputs.append((event_id, agent_name, dict(payload or {})))


def test_trade_event_workflow_records_decision_trace_memory_metrics():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        monkeypatch.setattr(
            mod,
            "resolve_intent",
            lambda **kwargs: ActionIntent(intent="increase", direction="long", confidence=Confidence(level="medium", score=0.7)),
        )
        monkeypatch.setattr(
            mod,
            "build_rule_plan",
            lambda **kwargs: RulePlan(intent=kwargs["intent"], sizing={"mode": "ratio", "order_size_ratio": 0.1}),
        )
        monkeypatch.setattr(mod, "strategy_gate_v2", lambda **kwargs: StrategyGateResult(allowed=True, reasons=[]))
        monkeypatch.setattr(
            mod,
            "risk_gate",
            lambda ctx: RiskAllowance(allow_open=True, allow_add=True, allow_reduce=True, allow_exit=True, reasons=[]),
        )
        monkeypatch.setattr(
            mod,
            "build_execution_plan",
            lambda **kwargs: ExecutionPlan(
                action="add",
                direction="long",
                allowance=kwargs["allowance"],
                confidence=Confidence(level="medium", score=0.7),
                sizing={"mode": "ratio", "order_size_ratio": 0.1},
                notes="ok",
            ),
        )

        memory = InMemorySymbolMemoryAdapter()
        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            recorder=recorder,
            symbol_memory_provider=memory,
            symbol_memory_recorder=memory,
        )
        await wf.run_with_result(
            TradeEventInput(
                event_id="evt-trace-mm-001",
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
        metrics = dict(trace_payload.get("memory_metrics") or {})
        assert metrics["memory_hit"] is False
        assert metrics["memory_raw_recent_count"] == 0
        assert metrics["memory_filtered_recent_count"] == 0
        contract_warnings = list(trace_payload.get("contract_warnings") or [])
        assert "state_features_semantic_contract_missing" in contract_warnings
        assert "msl_meta_schema_version_missing" in contract_warnings
        assert "state_features_alternative_source_provider_state_invalid" in contract_warnings
        assert "alternative_sources_conflict_detected" in contract_warnings
        assert "external_event_input_ignored" not in contract_warnings
        alert_codes = list(trace_payload.get("alert_codes") or [])
        assert "AGENT_ALTERNATIVE_SOURCES_CONFLICT" in alert_codes
        assert "AGENT_ALTERNATIVE_SOURCES_PROVIDER_STATE_INVALID" in alert_codes

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
