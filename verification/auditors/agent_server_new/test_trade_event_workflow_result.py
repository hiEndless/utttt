import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.domain.signal_decision_agent import SignalDecisionEvalResult
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
        return {"has_position": False}


class _Events:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return []


class _ExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        _ = payload
        return {"execution_action": "add", "reject_reason": None}


class _Recorder:
    def __init__(self) -> None:
        self.outputs = []

    async def record_market_context(self, event_id: str, payload):  # noqa: ANN001
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload):  # noqa: ANN001
        self.outputs.append((event_id, agent_name, dict(payload or {})))


class _CaptureLLMObserver:
    def __init__(self) -> None:
        self.payload = {}

    async def observe(self, payload):  # noqa: ANN001
        self.payload = dict(payload or {})
        return {
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content": '{"status":"ok","signal_verdict":"accept","signal_direction":"long","confidence":{"level":"high","score":0.86},"reasons":["onchain_flow_confirmation"]}',
        }


class _FailingLLMObserver:
    async def observe(self, payload):  # noqa: ANN001
        _ = payload
        raise RuntimeError("llm unavailable")


class _InjectedSignalDecisionAgent:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        _ = kwargs
        return SignalDecisionEvalResult(
            signal=SignalVerdict(direction="short", verdict="accept", confidence=Confidence(level="high", score=0.88)),
            decision_agent_key="onchain",
            decision_mode="rule",
            llm_parse_status="rule_only",
        )


def test_trade_event_workflow_run_with_result_returns_execution_result():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=_ExecutionDecider(),
            recorder=None,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-result-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        assert out.signal_decision.signal_verdict == "accept"
        assert out.execution_result == {"execution_action": "add", "reject_reason": None}

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_llm_observer_failed_still_fallbacks_to_rule_plan():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="short", verdict="accept", confidence=Confidence(level="medium", score=0.7)),
        )
        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=recorder,
            llm_observer=_FailingLLMObserver(),
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-llm-fail-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="short",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.signal_decision.decision_mode in {"rule", "rule_fallback"}
        assert out.signal_decision.llm_parse_status in {"llm_status_not_ok", "rule_only"}
        assert out.agent_plan.action == "add"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_uses_injected_signal_decision_agent():
    async def _run():
        injected = _InjectedSignalDecisionAgent()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            signal_decision_agent=injected,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-injected-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "wallet_alert", "source_category": "onchain"},
            )
        )
        assert injected.calls == 1
        assert out.signal_decision.decision_agent_key == "onchain"
        assert out.agent_plan.direction == "short"

    asyncio.run(_run())


def test_trade_event_workflow_llm_payload_is_trimmed_by_decision_agent_key():
    async def _run():
        observer = _CaptureLLMObserver()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            llm_observer=observer,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-llm-route-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "wallet_alert", "source_category": "onchain"},
            )
        )
        assert out.signal_decision.decision_mode in {"llm", "rule_fallback"}
        assert observer.payload.get("decision_agent_key") == "onchain"
        decision_prompt = dict(observer.payload.get("decision_prompt") or {})
        assert decision_prompt.get("focus") == "onchain_flow_validation"

    asyncio.run(_run())


def test_trade_event_workflow_records_minimal_stage_outputs():
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
            execution_decider=None,
            recorder=recorder,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        names = [name for _, name, _ in recorder.outputs]
        assert "workflow_bridge" in names
        assert "decision_trace" in names
        assert "intent_resolver" not in names
        assert "rule_planner" not in names
        assert "strategy_gate" not in names
        assert "execution_planner" not in names

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
