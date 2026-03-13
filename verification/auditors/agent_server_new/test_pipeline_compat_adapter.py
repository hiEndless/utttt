import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.contracts import Confidence, SignalDecision, SignalVerdict  # noqa: E402
from services.agent_server_new.domain.pipeline_compat_adapter import (  # noqa: E402
    build_decision_trace_legacy_sections,
    build_execution_decision_payload,
    build_legacy_stage_outputs,
    build_pipeline_compat_state,
    build_signal_decision_from_signal,
    build_symbol_memory_legacy_sections,
    build_workflow_bridge_payload,
)


def test_pipeline_compat_adapter_minimal_mode_returns_hold_state() -> None:
    signal = SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82))
    out = build_pipeline_compat_state(
        legacy_pipeline_enabled=False,
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    assert out.plan.action == "hold"
    assert out.plan.direction == "none"
    assert out.plan.confidence.level == "high"
    assert out.plan.confidence.score == 0.82
    assert out.intent.intent == "hold"
    assert out.rule_plan.notes == "legacy_pipeline_disabled"


def test_pipeline_compat_adapter_builds_legacy_stage_outputs_contract() -> None:
    signal = SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82))
    out = build_pipeline_compat_state(
        legacy_pipeline_enabled=False,
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    items = build_legacy_stage_outputs(state=out, cross_horizon={"suggested_policy": "no_action"})
    names = [name for name, _ in items]
    assert names == ["intent_resolver", "rule_planner", "horizon_policy_gate", "strategy_gate", "execution_planner"]
    trace_sections = build_decision_trace_legacy_sections(state=out)
    assert set(trace_sections.keys()) == {"intent", "rule_plan", "strategy_gate_result", "risk_gate"}
    memory_sections = build_symbol_memory_legacy_sections(state=out, cross_horizon={"suggested_policy": "no_action"})
    assert set(memory_sections.keys()) == {"cross_horizon_policy", "intent", "plan"}


def test_pipeline_compat_adapter_builds_execution_decision_payload_modes() -> None:
    signal_decision = SignalDecision(
        decision_id="evt-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal_direction="long",
        signal_verdict="accept",
        confidence=Confidence(level="medium", score=0.7),
        reliability_score=0.7,
        reasons=["ok"],
        evidence_refs=[],
        llm_observation={},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    plan_legacy = build_pipeline_compat_state(
        legacy_pipeline_enabled=False,
        signal=SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82)),
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    ).plan
    payload_legacy = build_execution_decision_payload(
        default_decision_id="evt-default",
        default_exchange="binance",
        default_symbol="ETHUSDT",
        signal_decision=signal_decision,
        plan=plan_legacy,
        pipeline_mode="legacy",
        cross_horizon={"suggested_policy": "no_action"},
    )
    assert payload_legacy["risk_hints"]["decision_confidence_source"] == "agent_execution_plan"

    signal_decision_min = SignalDecision(
        decision_id="evt-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal_direction="long",
        signal_verdict="accept",
        confidence=Confidence(level="medium", score=0.7),
        reliability_score=0.7,
        reasons=["ok"],
        evidence_refs=[],
        llm_observation={},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    payload_min = build_execution_decision_payload(
        default_decision_id="evt-default",
        default_exchange="binance",
        default_symbol="ETHUSDT",
        signal_decision=signal_decision_min,
        plan=plan_legacy,
        pipeline_mode="minimal",
        cross_horizon={"suggested_policy": "no_action"},
    )
    assert payload_min["risk_hints"]["decision_confidence_source"] == "agent_signal_decision"
    assert payload_min["risk_hints"]["agent_action_hint"] == "add"


def test_pipeline_compat_adapter_builds_workflow_bridge_payload() -> None:
    signal = SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82))
    state = build_pipeline_compat_state(
        legacy_pipeline_enabled=False,
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    signal_decision = SignalDecision(
        decision_id="evt-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal_direction="long",
        signal_verdict="accept",
        confidence=Confidence(level="high", score=0.82),
        reliability_score=0.82,
        reasons=["ok"],
        evidence_refs=[],
        llm_observation={},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    payload = build_workflow_bridge_payload(state=state, signal_decision=signal_decision, pipeline_mode="minimal")
    assert payload["pipeline_mode"] == "minimal"
    assert payload["decision"]["decision_agent_key"] == "technical"
    assert payload["execution_plan"]["action"] == "hold"
    assert payload["execution_plan"]["confidence"] == {"level": "high", "score": 0.82}


def test_pipeline_compat_adapter_builds_signal_decision_from_signal() -> None:
    signal = SignalVerdict(direction="short", verdict="accept", confidence=Confidence(level="medium", score=0.66))
    out = build_signal_decision_from_signal(
        decision_id="evt-signal-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal=signal,
        llm_observation={"status": "ok"},
        decision_agent_key="onchain",
        decision_mode="llm",
        llm_parse_status="llm_ok",
    )
    assert out.decision_id == "evt-signal-001"
    assert out.signal_direction == "short"
    assert out.signal_verdict == "accept"
    assert out.reliability_score == 0.66
    assert out.decision_agent_key == "onchain"
