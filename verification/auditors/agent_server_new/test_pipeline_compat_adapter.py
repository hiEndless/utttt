import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.contracts import Confidence, SignalVerdict  # noqa: E402
from services.agent_server_new.domain.pipeline_compat_adapter import (  # noqa: E402
    build_legacy_stage_outputs,
    build_pipeline_compat_state,
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
