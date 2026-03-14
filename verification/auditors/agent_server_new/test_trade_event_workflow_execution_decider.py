import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.domain.decision_plan_adapter import SIGNAL_DECISION_PLAN_NOTES
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


class _FailingExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        _ = payload
        raise RuntimeError("execution unavailable")


class _RejectingExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        _ = payload
        return {"execution_action": "hold", "reject_reason": "risk_limit_blocked"}


class _Recorder:
    def __init__(self) -> None:
        self.outputs = []

    async def record_market_context(self, event_id: str, payload):  # noqa: ANN001
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload):  # noqa: ANN001
        self.outputs.append((event_id, agent_name, dict(payload or {})))


def test_trade_event_workflow_calls_execution_decider():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
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
        assert "confidence" not in decider.payload
        assert decider.payload["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["risk_hints"]["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["risk_hints"]["decision_confidence_source"] == "agent_signal_decision"
        assert decider.payload["risk_hints"]["decision_agent_key"] == "technical"
        assert decider.payload["risk_hints"]["decision_mode"] == "rule"
        assert decider.payload["risk_hints"]["llm_parse_status"] == "rule_only"
        assert decider.payload["risk_hints"]["prompt_config_source"] == "runtime"
        assert isinstance(decider.payload["risk_hints"]["prompt_config_version"], str)
        assert "execution_hint" not in decider.payload
        assert "adaptive_profile" not in decider.payload

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_calls_execution_decider_without_ai_adaptive_reserved_fields():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
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
                event_id="evt-exec-002",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.action == "add"
        assert decider.called is True
        assert "execution_hint" not in decider.payload
        assert "adaptive_profile" not in decider.payload
        assert "adaptive_profile_version" not in decider.payload
        assert "adaptive_explain" not in decider.payload

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_pipeline_still_calls_execution_decider():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
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
                event_id="evt-exec-minimal-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.action == "add"
        assert decider.called is True
        assert decider.payload["decision_id"] == "evt-exec-minimal-001"
        assert decider.payload["risk_hints"]["agent_action_hint"] == "add"
        assert decider.payload["risk_hints"]["agent_notes"] == SIGNAL_DECISION_PLAN_NOTES
        assert decider.payload["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["risk_hints"]["decision_confidence"] == {"level": "medium", "score": 0.7}
        assert decider.payload["risk_hints"]["decision_confidence_source"] == "agent_signal_decision"
        assert decider.payload["risk_hints"]["decision_mode"] == "rule"
        assert decider.payload["risk_hints"]["llm_parse_status"] == "rule_only"
        assert decider.payload["risk_hints"]["prompt_config_source"] == "runtime"
        assert isinstance(decider.payload["risk_hints"]["prompt_config_version"], str)

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_records_execution_decider_error_when_unavailable():
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
            execution_decider=_FailingExecutionDecider(),
            recorder=recorder,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-exec-fail-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.execution_result is None
        rows = [x for x in recorder.outputs if x[1] == "execution_decider"]
        assert rows
        payload = rows[-1][2]
        assert payload.get("status") == "error"
        assert payload.get("error_type") == "RuntimeError"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_records_execution_reject_result_as_business_outcome():
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
            execution_decider=_RejectingExecutionDecider(),
            recorder=recorder,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-exec-reject-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.execution_result is not None
        assert out.execution_result.get("execution_action") == "hold"
        assert out.execution_result.get("reject_reason") == "risk_limit_blocked"
        rows = [x for x in recorder.outputs if x[1] == "execution_decider"]
        assert rows
        payload = rows[-1][2]
        assert payload.get("execution_action") == "hold"
        assert payload.get("reject_reason") == "risk_limit_blocked"
        assert payload.get("status") is None

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_blocks_noncanonical_none_direction_intent_before_execution():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        original_builder = mod.build_execution_decision_payload

        def _noncanonical_none_payload_builder(**kwargs):  # noqa: ANN001
            payload = original_builder(**kwargs)
            payload["direction_intent"] = "none"
            return payload

        monkeypatch.setattr(mod, "build_execution_decision_payload", _noncanonical_none_payload_builder)
        recorder = _Recorder()
        decider = _ExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=decider,
            recorder=recorder,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-exec-block-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.execution_result is None
        assert decider.called is False
        rows = [x for x in recorder.outputs if x[1] == "execution_decider"]
        assert rows
        payload = rows[-1][2]
        assert payload.get("status") == "blocked"
        assert payload.get("error_type") == "InvalidDirectionIntent"
        assert payload.get("direction_intent") == "none"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
