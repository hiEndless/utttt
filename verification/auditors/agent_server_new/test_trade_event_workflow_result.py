import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import (
    TradeEventInput,
    TradeEventWorkflow,
)
from services.agent_server_new.domain.contracts import ActionIntent, Confidence, ExecutionPlan, RiskAllowance, RulePlan, SignalVerdict
from services.agent_server_new.domain.signal_decision_agent import SignalDecisionEvalResult
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


class _EventsForLLMRoute:
    async def get_active_events(self, exchange: str, symbol: str):
        _ = (exchange, symbol)
        return [
            {"type": "social_trending", "score": 0.92, "source": "social"},
            {"type": "wallet_alert", "score": 0.80, "evidence": {"event_source_category": "onchain"}},
            {"type": "exchange_flow_spike", "score": 0.70, "source": "onchain_provider"},
            {"type": "macro_news", "score": 0.60, "source": "news"},
        ]


class _MarketStateForLLMRoute(_MarketState):
    async def get_market_state(self, exchange: str, symbol: str):
        out = await super().get_market_state(exchange, symbol)
        return MarketStateSnapshot(
            exchange=out.exchange,
            symbol=out.symbol,
            msl=out.msl,
            msl_meta=out.msl_meta,
            cross_horizon=out.cross_horizon,
            state_features={
                "evidence": {},
                "anomalies": {},
                "features": {
                    "social_sentiment_score": 0.82,
                    "wallet_netflow_score": 0.77,
                },
            },
        )


class _ExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        _ = payload
        return {
            "execution_action": "add",
            "reject_reason": None,
            "applied_risk_rules": [],
        }


class _FailingLLMObserver:
    async def observe(self, payload):  # noqa: ANN001
        _ = payload
        raise RuntimeError("llm observer unavailable")


class _InvalidStatusLLMObserver:
    async def observe(self, payload):  # noqa: ANN001
        _ = payload
        return {
            "status": "unknown_status",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content": "{}",
        }


class _StructuredLLMObserver:
    async def observe(self, payload):  # noqa: ANN001
        _ = payload
        return {
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content": "{\"signal_verdict\":\"accept\",\"signal_direction\":\"short\",\"confidence_score\":0.83,\"reasons\":[\"social_breaking_news\"]}",
        }


class _CaptureLLMObserver:
    def __init__(self) -> None:
        self.payload = {}

    async def observe(self, payload):  # noqa: ANN001
        self.payload = dict(payload or {})
        return {
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content": "{\"signal_verdict\":\"accept\",\"signal_direction\":\"long\",\"confidence_score\":0.76,\"reasons\":[\"ok\"]}",
        }


class _RouteCaptureLLMObserver:
    def __init__(self) -> None:
        self.calls = []

    async def observe(self, payload):  # noqa: ANN001
        body = dict(payload or {})
        self.calls.append(body)
        return {
            "status": "ok",
            "provider": "openai_compatible",
            "model": str((body.get("decision_prompt") or {}).get("model_id") or "gpt-default"),
            "raw_content": (
                "{\"signal_verdict\":\"accept\","
                f"\"signal_direction\":\"{str(body.get('signal_direction') or 'none')}\","
                "\"confidence_score\":0.79,\"reasons\":[\"route_model_ok\"]}"
            ),
        }


class _CaptureExecutionDecider:
    def __init__(self) -> None:
        self.payloads = []

    async def decide(self, payload):  # noqa: ANN001
        body = dict(payload or {})
        self.payloads.append(body)
        return {
            "execution_action": "add",
            "reject_reason": None,
            "applied_risk_rules": [],
        }


class _Recorder:
    def __init__(self) -> None:
        self.outputs = []

    async def record_market_context(self, event_id: str, payload):  # noqa: ANN001
        _ = (event_id, payload)

    async def record_agent_output(self, event_id: str, agent_name: str, payload):  # noqa: ANN001
        self.outputs.append((event_id, agent_name, dict(payload or {})))


class _SignalDecisionAgent:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, **kwargs):  # noqa: ANN003
        self.calls += 1
        _ = kwargs
        return SignalDecisionEvalResult(
            signal=SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.9)),
            decision_agent_key="onchain",
        )


def test_trade_event_workflow_run_with_result_returns_execution_result():
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
        assert out.signal_decision.signal_direction == "long"
        assert out.signal_decision.decision_id == "evt-result-001"
        assert out.signal_decision.decision_agent_key == "technical"
        assert out.signal_decision.reliability_score == 0.7
        assert out.execution_result is not None
        assert out.execution_result["execution_action"] == "add"

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
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            llm_observer=_FailingLLMObserver(),
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-llm-fallback-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        assert out.signal_decision.signal_verdict == "accept"
        assert out.signal_decision.signal_direction == "long"
        assert out.signal_decision.decision_agent_key == "technical"
        assert out.signal_decision.llm_observation["status"] == "error"
        assert out.execution_result is None

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_decision_trace_schema_guard_warn_only():
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

        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=recorder,
            llm_observer=_InvalidStatusLLMObserver(),
            decision_trace_schema_validate=True,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-trace-guard-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        names = [name for _, name, _ in recorder.outputs]
        assert "decision_trace_schema_guard" in names
        assert "decision_trace" in names

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_uses_injected_signal_decision_agent():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

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
                confidence=Confidence(level="high", score=0.9),
                sizing={"mode": "ratio", "order_size_ratio": 0.1},
                notes="ok",
            ),
        )
        signal_agent = _SignalDecisionAgent()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            signal_decision_agent=signal_agent,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-signal-agent-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "whale_onchain_alert"},
            )
        )
        assert signal_agent.calls == 1
        assert out.signal_decision.decision_agent_key == "onchain"
        assert out.signal_decision.reliability_score == 0.9

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_hybrid_signal_decision_agent_prefers_llm():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "resolve_intent",
            lambda **kwargs: ActionIntent(intent="increase", direction="short", confidence=Confidence(level="medium", score=0.7)),
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
                direction="short",
                allowance=kwargs["allowance"],
                confidence=Confidence(level="high", score=0.83),
                sizing={"mode": "ratio", "order_size_ratio": 0.1},
                notes="ok",
            ),
        )
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
            llm_observer=_StructuredLLMObserver(),
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-hybrid-llm-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "social_news_signal"},
            )
        )
        assert out.signal_decision.decision_mode == "llm"
        assert out.signal_decision.llm_parse_status == "llm_ok"
        assert out.signal_decision.signal_direction == "short"
        assert out.signal_decision.signal_verdict == "accept"
        assert out.signal_decision.reliability_score == 0.83

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_can_disable_legacy_pipeline_path():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "resolve_intent",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("should not call resolve_intent")),
        )
        monkeypatch.setattr(
            mod,
            "build_rule_plan",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("should not call build_rule_plan")),
        )

        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=_Recorder(),
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-legacy-off-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"
        assert out.agent_plan.direction == "long"
        assert out.agent_plan.confidence.level == out.signal_decision.confidence.level
        assert out.agent_plan.confidence.score == out.signal_decision.confidence.score
        assert out.agent_plan.notes == "minimal_pipeline_semantic_plan"
        trace_payload = {}
        for _, name, payload in wf._recorder.outputs:  # noqa: SLF001
            if name == "decision_trace":
                trace_payload = payload
                break
        assert trace_payload
        routing = dict(trace_payload.get("routing") or {})
        assert routing.get("pipeline_mode") == "minimal"
        assert routing.get("event_type_raw") == "indicator_signal"
        assert routing.get("event_type_normalized") == "market_indicator_signal"
        assert routing.get("event_type_match_mode") == "alias"
        names = [name for _, name, _ in wf._recorder.outputs]  # noqa: SLF001
        assert "workflow_bridge" in names
        bridge_payload = {}
        for _, name, payload in wf._recorder.outputs:  # noqa: SLF001
            if name == "workflow_bridge":
                bridge_payload = dict(payload or {})
                break
        execution_plan_payload = dict(bridge_payload.get("execution_plan") or {})
        confidence_payload = dict(execution_plan_payload.get("confidence") or {})
        assert confidence_payload.get("level") == out.signal_decision.confidence.level
        assert confidence_payload.get("score") == out.signal_decision.confidence.score
        assert "intent_resolver" not in names
        assert "rule_planner" not in names
        assert "horizon_policy_gate" not in names
        assert "strategy_gate" not in names
        assert "execution_planner" not in names

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_llm_payload_is_trimmed_by_decision_agent_key():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

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
        observer = _CaptureLLMObserver()
        wf = TradeEventWorkflow(
            market_state=_MarketStateForLLMRoute(),
            position_context=_Position(),
            active_events=_EventsForLLMRoute(),
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
        assert out.signal_decision.decision_mode == "llm"
        assert observer.payload.get("decision_agent_key") == "onchain"
        decision_prompt = dict(observer.payload.get("decision_prompt") or {})
        assert decision_prompt.get("focus") == "onchain_flow_validation"
        active_events = list(observer.payload.get("active_events") or [])
        assert active_events
        first_type = str((active_events[0] or {}).get("type") or "")
        assert first_type in {"wallet_alert", "exchange_flow_spike"}
        kf = dict(observer.payload.get("key_market_features") or {})
        names = [str((x or {}).get("name") or "") for x in list(kf.get("features") or [])]
        assert "alternative_source_summary" in names

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_mode_skips_horizon_policy_config_loading():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "load_horizon_policy_config_from_env",
            lambda: (_ for _ in ()).throw(RuntimeError("should not load horizon config in minimal mode")),
        )
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=None,
            recorder=None,
        )
        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-no-horizon-load-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.agent_plan.action == "add"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_business_closed_loop_example():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82)),
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
                event_id="evt-minimal-closed-loop-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        assert out.signal_decision.signal_verdict == "accept"
        assert out.signal_decision.signal_direction == "long"
        assert out.execution_result is not None
        assert out.execution_result.get("execution_action") == "add"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_multi_event_route_model_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {"focus": "generic_signal_validation", "checklist": [], "avoid": []},
                "technical": {
                    "focus": "technical_signal_validation",
                    "checklist": ["trend_structure"],
                    "avoid": ["execution_action"],
                    "model_id": "gpt-tech-mini",
                },
                "social_news": {
                    "focus": "social_news_event_validation",
                    "checklist": ["source_credibility"],
                    "avoid": ["single_post_overweight"],
                    "model_id": "gpt-social-mini",
                },
            },
        )

        out_tech = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-multi-route-tech-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        out_social = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-multi-route-social-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="short",
                payload={"event_type": "social_news_signal"},
            )
        )

        assert out_tech.signal_decision.decision_agent_key == "technical"
        assert out_social.signal_decision.decision_agent_key == "social_news"
        assert out_tech.execution_result is not None
        assert out_social.execution_result is not None
        assert out_tech.execution_result.get("execution_action") == "add"
        assert out_social.execution_result.get("execution_action") == "add"

        by_event = {str((x or {}).get("event_id") or ""): dict(x or {}) for x in observer.calls}
        tech_prompt = dict((by_event.get("evt-multi-route-tech-001") or {}).get("decision_prompt") or {})
        social_prompt = dict((by_event.get("evt-multi-route-social-001") or {}).get("decision_prompt") or {})
        assert tech_prompt.get("model_id") == "gpt-tech-mini"
        assert social_prompt.get("model_id") == "gpt-social-mini"

        assert len(execution_decider.payloads) == 2
        risk_hints_tech = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        risk_hints_social = dict((execution_decider.payloads[1] or {}).get("risk_hints") or {})
        assert risk_hints_tech.get("decision_agent_key") == "technical"
        assert risk_hints_social.get("decision_agent_key") == "social_news"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_unknown_event_falls_back_to_generic_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="none", verdict="uncertain", confidence=Confidence(level="low", score=0.4)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {
                    "focus": "generic_signal_validation",
                    "checklist": ["direction_consistency"],
                    "avoid": ["execution_action"],
                    "model_id": "gpt-generic-mini",
                },
                "technical": {"focus": "technical_signal_validation", "checklist": [], "avoid": []},
                "social_news": {"focus": "social_news_event_validation", "checklist": [], "avoid": []},
                "onchain": {"focus": "onchain_flow_validation", "checklist": [], "avoid": []},
                "liquidation": {"focus": "liquidation_shock_validation", "checklist": [], "avoid": []},
            },
        )

        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-unknown-route-generic-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "xfeed_alert_alpha"},
            )
        )

        assert out.signal_decision.decision_agent_key == "generic"
        assert out.execution_result is not None
        assert out.execution_result.get("execution_action") == "add"

        assert len(observer.calls) == 1
        llm_payload = dict(observer.calls[0] or {})
        assert llm_payload.get("decision_agent_key") == "generic"
        prompt = dict(llm_payload.get("decision_prompt") or {})
        assert prompt.get("focus") == "generic_signal_validation"
        assert prompt.get("model_id") == "gpt-generic-mini"

        assert len(execution_decider.payloads) == 1
        risk_hints = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        assert risk_hints.get("decision_agent_key") == "generic"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_selected_type_overrides_event_type_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="short", verdict="accept", confidence=Confidence(level="high", score=0.81)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {"focus": "generic_signal_validation", "checklist": [], "avoid": []},
                "technical": {
                    "focus": "technical_signal_validation",
                    "checklist": ["trend_structure"],
                    "avoid": ["execution_action"],
                    "model_id": "gpt-tech-mini",
                },
                "social_news": {
                    "focus": "social_news_event_validation",
                    "checklist": ["source_credibility"],
                    "avoid": ["single_post_overweight"],
                    "model_id": "gpt-social-mini",
                },
                "onchain": {"focus": "onchain_flow_validation", "checklist": [], "avoid": []},
                "liquidation": {"focus": "liquidation_shock_validation", "checklist": [], "avoid": []},
            },
        )

        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-selected-type-priority-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="short",
                payload={
                    "selected_type": "social_news",
                    "event_type": "indicator_signal",
                },
            )
        )

        assert out.signal_decision.decision_agent_key == "social_news"
        assert out.execution_result is not None
        assert out.execution_result.get("execution_action") == "add"

        assert len(observer.calls) == 1
        llm_payload = dict(observer.calls[0] or {})
        assert llm_payload.get("decision_agent_key") == "social_news"
        prompt = dict(llm_payload.get("decision_prompt") or {})
        assert prompt.get("model_id") == "gpt-social-mini"

        assert len(execution_decider.payloads) == 1
        risk_hints = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        assert risk_hints.get("decision_agent_key") == "social_news"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_source_category_fallback_route_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.8)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {"focus": "generic_signal_validation", "checklist": [], "avoid": []},
                "technical": {
                    "focus": "technical_signal_validation",
                    "checklist": ["trend_alignment"],
                    "avoid": [],
                    "model_id": "gpt-technical-mini",
                },
                "social_news": {
                    "focus": "social_news_event_validation",
                    "checklist": ["source_credibility"],
                    "avoid": ["single_post_overweight"],
                    "model_id": "gpt-social-mini",
                },
                "onchain": {
                    "focus": "onchain_flow_validation",
                    "checklist": ["wallet_flow_direction"],
                    "avoid": ["execution_action"],
                    "model_id": "gpt-onchain-mini",
                },
                "liquidation": {"focus": "liquidation_shock_validation", "checklist": [], "avoid": []},
            },
        )

        out_onchain = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-source-category-onchain-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "xfeed_unknown_a", "source_category": "onchain"},
            )
        )
        out_news = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-source-category-news-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="short",
                payload={"event_type": "xfeed_unknown_b", "source_category": "news"},
            )
        )
        out_market = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-source-category-market-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "xfeed_unknown_c", "source_category": "market"},
            )
        )

        assert out_onchain.signal_decision.decision_agent_key == "onchain"
        assert out_news.signal_decision.decision_agent_key == "social_news"
        assert out_market.signal_decision.decision_agent_key == "technical"
        assert out_onchain.execution_result is not None
        assert out_news.execution_result is not None
        assert out_market.execution_result is not None

        by_event = {str((x or {}).get("event_id") or ""): dict(x or {}) for x in observer.calls}
        prompt_onchain = dict((by_event.get("evt-source-category-onchain-001") or {}).get("decision_prompt") or {})
        prompt_news = dict((by_event.get("evt-source-category-news-001") or {}).get("decision_prompt") or {})
        prompt_market = dict((by_event.get("evt-source-category-market-001") or {}).get("decision_prompt") or {})
        assert prompt_onchain.get("model_id") == "gpt-onchain-mini"
        assert prompt_news.get("model_id") == "gpt-social-mini"
        assert prompt_market.get("model_id") == "gpt-technical-mini"

        assert len(execution_decider.payloads) == 3
        risk_hints_onchain = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        risk_hints_news = dict((execution_decider.payloads[1] or {}).get("risk_hints") or {})
        risk_hints_market = dict((execution_decider.payloads[2] or {}).get("risk_hints") or {})
        assert risk_hints_onchain.get("decision_agent_key") == "onchain"
        assert risk_hints_news.get("decision_agent_key") == "social_news"
        assert risk_hints_market.get("decision_agent_key") == "technical"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_source_object_category_fallback_route_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.8)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {"focus": "generic_signal_validation", "checklist": [], "avoid": []},
                "technical": {"focus": "technical_signal_validation", "checklist": [], "avoid": []},
                "social_news": {"focus": "social_news_event_validation", "checklist": [], "avoid": []},
                "onchain": {
                    "focus": "onchain_flow_validation",
                    "checklist": ["wallet_flow_direction"],
                    "avoid": ["execution_action"],
                    "model_id": "gpt-onchain-mini",
                },
                "liquidation": {"focus": "liquidation_shock_validation", "checklist": [], "avoid": []},
            },
        )

        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-source-obj-category-onchain-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={
                    "event_type": "xfeed_unknown_obj",
                    "source": {"category": "onchain", "name": "glassnode"},
                },
            )
        )

        assert out.signal_decision.decision_agent_key == "onchain"
        assert out.execution_result is not None
        assert out.execution_result.get("execution_action") == "add"

        assert len(observer.calls) == 1
        llm_payload = dict(observer.calls[0] or {})
        assert llm_payload.get("decision_agent_key") == "onchain"
        prompt = dict(llm_payload.get("decision_prompt") or {})
        assert prompt.get("model_id") == "gpt-onchain-mini"

        assert len(execution_decider.payloads) == 1
        risk_hints = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        assert risk_hints.get("decision_agent_key") == "onchain"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_signal_source_type_route_closed_loop():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.8)),
        )
        observer = _RouteCaptureLLMObserver()
        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=observer,
            signal_decision_prompt_profiles={
                "generic": {"focus": "generic_signal_validation", "checklist": [], "avoid": []},
                "technical": {"focus": "technical_signal_validation", "checklist": [], "avoid": []},
                "social_news": {"focus": "social_news_event_validation", "checklist": [], "avoid": []},
                "onchain": {"focus": "onchain_flow_validation", "checklist": [], "avoid": []},
                "liquidation": {"focus": "liquidation_shock_validation", "checklist": [], "avoid": []},
            },
        )

        cases = [
            ("evt-source-type-tech-001", "market_indicator", "technical"),
            ("evt-source-type-tech-002", "market_indicator_signal", "technical"),
            ("evt-source-type-onchain-001", "onchain_wallet", "onchain"),
            ("evt-source-type-onchain-002", "onchain_wallet_anomaly", "onchain"),
            ("evt-source-type-liq-001", "large_liquidation", "liquidation"),
            ("evt-source-type-liq-002", "market_large_liquidation", "liquidation"),
            ("evt-source-type-social-001", "social_news", "social_news"),
            ("evt-source-type-social-002", "macro_news", "social_news"),
        ]
        for event_id, source_type, expected_agent_key in cases:
            out = await wf.run_with_result(
                TradeEventInput(
                    event_id=event_id,
                    exchange="binance",
                    symbol="ETHUSDT",
                    signal_direction="long",
                    payload={
                        "event_type": "xfeed_unknown_source_type",
                        "signal_source_type": source_type,
                    },
                )
            )
            assert out.signal_decision.decision_agent_key == expected_agent_key
            assert out.execution_result is not None
            assert out.execution_result.get("execution_action") == "add"

        by_event = {str((x or {}).get("event_id") or ""): dict(x or {}) for x in observer.calls}
        for event_id, _, expected_agent_key in cases:
            llm_payload = dict(by_event.get(event_id) or {})
            assert llm_payload.get("decision_agent_key") == expected_agent_key

        assert len(execution_decider.payloads) == len(cases)
        for i, (_, _, expected_agent_key) in enumerate(cases):
            risk_hints = dict((execution_decider.payloads[i] or {}).get("risk_hints") or {})
            assert risk_hints.get("decision_agent_key") == expected_agent_key

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_llm_reject_or_uncertain_maps_action_hint_hold():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.9)),
        )

        class _RejectOrUncertainObserver:
            def __init__(self) -> None:
                self._i = 0

            async def observe(self, payload):  # noqa: ANN001
                _ = payload
                self._i += 1
                if self._i == 1:
                    content = "{\"signal_verdict\":\"reject\",\"signal_direction\":\"long\",\"confidence_score\":0.72,\"reasons\":[\"evidence_conflict\"]}"
                else:
                    content = "{\"signal_verdict\":\"uncertain\",\"signal_direction\":\"none\",\"confidence_score\":0.61,\"reasons\":[\"insufficient_consensus\"]}"
                return {
                    "status": "ok",
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "raw_content": content,
                }

        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=_RejectOrUncertainObserver(),
        )

        out_reject = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-reject-hold-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        out_uncertain = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-uncertain-hold-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )

        assert out_reject.signal_decision.signal_verdict == "reject"
        assert out_uncertain.signal_decision.signal_verdict == "uncertain"
        assert out_reject.execution_result is not None
        assert out_uncertain.execution_result is not None

        assert len(execution_decider.payloads) == 2
        risk_hints_reject = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        risk_hints_uncertain = dict((execution_decider.payloads[1] or {}).get("risk_hints") or {})
        assert risk_hints_reject.get("agent_action_hint") == "hold"
        assert risk_hints_uncertain.get("agent_action_hint") == "hold"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_llm_accept_valid_direction_maps_action_hint_add():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="none", verdict="uncertain", confidence=Confidence(level="low", score=0.3)),
        )

        class _AcceptObserver:
            def __init__(self) -> None:
                self._i = 0

            async def observe(self, payload):  # noqa: ANN001
                _ = payload
                self._i += 1
                if self._i == 1:
                    content = "{\"signal_verdict\":\"accept\",\"signal_direction\":\"long\",\"confidence_score\":0.81,\"reasons\":[\"trend_align\"]}"
                else:
                    content = "{\"signal_verdict\":\"accept\",\"signal_direction\":\"short\",\"confidence_score\":0.78,\"reasons\":[\"breakdown_confirmed\"]}"
                return {
                    "status": "ok",
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "raw_content": content,
                }

        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=_AcceptObserver(),
        )

        out_long = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-accept-add-long-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )
        out_short = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-accept-add-short-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="short",
                payload={"event_type": "indicator_signal"},
            )
        )

        assert out_long.signal_decision.signal_verdict == "accept"
        assert out_short.signal_decision.signal_verdict == "accept"
        assert out_long.execution_result is not None
        assert out_short.execution_result is not None

        assert len(execution_decider.payloads) == 2
        risk_hints_long = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        risk_hints_short = dict((execution_decider.payloads[1] or {}).get("risk_hints") or {})
        assert risk_hints_long.get("agent_action_hint") == "add"
        assert risk_hints_short.get("agent_action_hint") == "add"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()


def test_trade_event_workflow_minimal_llm_accept_none_direction_maps_action_hint_hold():
    async def _run(monkeypatch):  # noqa: ANN001
        import services.agent_server_new.app.workflows.trade_event_workflow as mod

        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.9)),
        )

        class _AcceptNoneDirectionObserver:
            async def observe(self, payload):  # noqa: ANN001
                _ = payload
                return {
                    "status": "ok",
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "raw_content": (
                        "{\"signal_verdict\":\"accept\",\"signal_direction\":\"none\","
                        "\"confidence_score\":0.73,\"reasons\":[\"direction_not_confirmed\"]}"
                    ),
                }

        execution_decider = _CaptureExecutionDecider()
        wf = TradeEventWorkflow(
            market_state=_MarketState(),
            position_context=_Position(),
            active_events=_Events(),
            execution_decider=execution_decider,
            recorder=None,
            llm_observer=_AcceptNoneDirectionObserver(),
        )

        out = await wf.run_with_result(
            TradeEventInput(
                event_id="evt-minimal-accept-none-hold-001",
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "indicator_signal"},
            )
        )

        assert out.signal_decision.signal_verdict == "accept"
        assert out.signal_decision.signal_direction == "none"
        assert out.execution_result is not None

        assert len(execution_decider.payloads) == 1
        risk_hints = dict((execution_decider.payloads[0] or {}).get("risk_hints") or {})
        assert risk_hints.get("agent_action_hint") == "hold"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
