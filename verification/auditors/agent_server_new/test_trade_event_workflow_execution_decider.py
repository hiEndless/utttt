import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
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
            msl_meta={"schema_version": 2, "inference_version": "msl_generator_v2"},
            cross_horizon={
                "alignment": "aligned",
                "suggested_policy": "follow_long_term",
                "policy_reason": "timeframe_aligned",
            },
            state_features={"evidence": {}, "anomalies": {}},
        )


class _Position:
    async def get_position_context(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return {"has_position": False}


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return []


class _ExecutionDecider:
    def __init__(self) -> None:
        self.called = False
        self.payload = {}

    async def decide(self, payload):  # noqa: ANN001
        self.called = True
        self.payload = dict(payload or {})
        return {"execution_action": "add", "reject_reason": None}


def test_trade_event_workflow_calls_execution_decider():
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

        decider = _ExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=decider,
            recorder=None,
        )
        out = await wf.run(
            TradeEventInput(
                event_id="evt-exec-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.action == "add"
        assert decider.called is True
        assert decider.payload["decision_id"] == "evt-exec-001"
        assert decider.payload["direction_intent"] == "long"
        assert decider.payload["confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["risk_hints"]["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert "execution_hint" not in decider.payload
        assert "adaptive_profile" not in decider.payload

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_calls_execution_decider_with_ai_adaptive_reserved_fields():
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

        decider = _ExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=decider,
            recorder=None,
            ai_adaptive_enabled=True,
            ai_adaptive_mode="recommend",
        )
        out = await wf.run(
            TradeEventInput(
                event_id="evt-exec-002",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.action == "add"
        assert decider.called is True
        assert decider.payload["execution_hint"]["adaptive_mode"] == "recommend"
        assert decider.payload["adaptive_profile_version"] == "reserved-v0"
        assert decider.payload["adaptive_explain"]["status"] == "reserved_only"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
