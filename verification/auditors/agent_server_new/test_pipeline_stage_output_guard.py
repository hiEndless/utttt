import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.contracts import Confidence, SignalVerdict  # noqa: E402
from services.agent_server_new.domain.pipeline_compat_adapter import (  # noqa: E402
    build_pipeline_compat_state,
    build_recorder_stage_payloads,
    build_signal_decision_from_signal,
)


def _sample_state_and_decision():
    signal = SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.82))
    state = build_pipeline_compat_state(
        signal=signal,
        msl=None,  # type: ignore[arg-type]
        position_context={},
        active_events=[],
        signal_event={},
        cross_horizon={},
    )
    decision = build_signal_decision_from_signal(
        decision_id="evt-stage-guard-001",
        exchange="binance",
        symbol="ETHUSDT",
        signal=signal,
        llm_observation={},
        decision_agent_key="technical",
        decision_mode="rule",
        llm_parse_status="rule_only",
    )
    return state, decision


def test_pipeline_stage_output_guard_minimal_mode_keys_are_frozen() -> None:
    state, decision = _sample_state_and_decision()
    out = build_recorder_stage_payloads(
        state=state,
        signal_decision=decision,
        pipeline_mode="minimal",
        cross_horizon={"suggested_policy": "no_action"},
        decision_trace_payload={"event_id": "evt-stage-guard-001"},
    )
    assert set(out.keys()) == {"workflow_bridge", "decision_trace"}
