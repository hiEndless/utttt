import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.contracts import Confidence, SignalDecision, SignalVerdict  # noqa: E402
from services.agent_server_new.domain.pipeline_compat_adapter import (  # noqa: E402
    build_decision_trace_payload,
    build_decision_trace_semantic_sections,
    build_execution_decision_payload,
    build_pipeline_compat_state,
    build_recorder_stage_payloads,
    build_signal_decision_from_signal,
    build_symbol_memory_record_payload,
    build_symbol_memory_semantic_sections,
    build_workflow_bridge_payload,
)


def _sample_signal() -> SignalVerdict:
    return SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82))


def test_pipeline_compat_adapter_minimal_semantic_state() -> None:
    out = build_pipeline_compat_state(
        signal=_sample_signal(),
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    assert out.plan.action == "add"
    assert out.plan.direction == "long"
    assert out.rule_plan.notes == "minimal_pipeline_semantic_plan"


def test_pipeline_compat_adapter_semantic_sections_contract() -> None:
    out = build_pipeline_compat_state(
        signal=_sample_signal(),
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    trace_sections = build_decision_trace_semantic_sections(state=out)
    assert set(trace_sections.keys()) == {"intent", "rule_plan", "strategy_gate_result", "risk_gate"}
    memory_sections = build_symbol_memory_semantic_sections(state=out, cross_horizon={"suggested_policy": "no_action"})
    assert set(memory_sections.keys()) == {"cross_horizon_policy", "intent", "plan"}


def test_pipeline_compat_adapter_builds_execution_decision_payload() -> None:
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
    plan = build_pipeline_compat_state(
        signal=_sample_signal(),
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    ).plan
    payload = build_execution_decision_payload(
        default_decision_id="evt-default",
        default_exchange="binance",
        default_symbol="ETHUSDT",
        signal_decision=signal_decision,
        plan=plan,
        cross_horizon={"suggested_policy": "no_action"},
    )
    assert payload["risk_hints"]["decision_confidence_source"] == "agent_signal_decision"
    assert payload["risk_hints"]["agent_action_hint"] == "add"


def test_pipeline_compat_adapter_builds_workflow_bridge_payload() -> None:
    state = build_pipeline_compat_state(
        signal=_sample_signal(),
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
    payload = build_workflow_bridge_payload(state=state, signal_decision=signal_decision)
    assert payload["pipeline_mode"] == "minimal"
    assert payload["execution_plan"]["action"] == "add"


def test_pipeline_compat_adapter_builds_decision_trace_payload() -> None:
    signal = _sample_signal()
    state = build_pipeline_compat_state(
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    signal_decision = build_signal_decision_from_signal(
        decision_id="evt-trace-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal=signal,
        llm_observation={"status": "disabled"},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    trace = build_decision_trace_payload(
        event_id="evt-trace-001",
        exchange="binance",
        symbol="ETHUSDT",
        ts=123,
        signal_event={"payload": {"event_type": "indicator_signal"}},
        msl={"summary": "ok"},
        key_market_features={"features": [], "contract_warnings": []},
        signal=signal,
        signal_decision=signal_decision,
        pipeline_mode="minimal",
        llm_contract_error_code="",
        llm_contract_errors=[],
        router_config_source="runtime",
        router_config_version="v1",
        prompt_config_source="runtime",
        prompt_config_version="v1",
        event_type_diag={"raw_event_type": "indicator_signal", "normalized_event_type": "market_indicator_signal", "matched": "alias"},
        state=state,
        llm_observation={"status": "disabled"},
    )
    assert trace["routing"]["pipeline_mode"] == "minimal"
    assert trace["execution_plan"]["action"] == "add"


def test_pipeline_compat_adapter_builds_recorder_stage_payloads_for_minimal() -> None:
    state = build_pipeline_compat_state(
        signal=_sample_signal(),
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    signal_decision = build_signal_decision_from_signal(
        decision_id="evt-rec-min-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal=_sample_signal(),
        llm_observation={},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    out = build_recorder_stage_payloads(
        state=state,
        signal_decision=signal_decision,
        pipeline_mode="minimal",
        cross_horizon={"suggested_policy": "no_action"},
        decision_trace_payload={"event_id": "evt-rec-min-001"},
    )
    assert set(out.keys()) == {"workflow_bridge", "decision_trace"}


def test_pipeline_compat_adapter_builds_symbol_memory_record_payload() -> None:
    signal = _sample_signal()
    state = build_pipeline_compat_state(
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
        horizon_policy_config={},
    )
    payload = build_symbol_memory_record_payload(
        ts=123,
        event_id="evt-memory-001",
        signal_event={"payload": {"event_type": "indicator_signal"}},
        msl_summary="ok",
        signal=signal,
        state=state,
        cross_horizon={"suggested_policy": "no_action"},
        contract_warnings=["state_features_semantic_contract_missing"],
        execution_result={"execution_action": "add"},
    )
    assert payload["event_id"] == "evt-memory-001"
    assert payload["plan"]["action"] == "add"
    assert payload["intent"]["intent"] == "increase"
