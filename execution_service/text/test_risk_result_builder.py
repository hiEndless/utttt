from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.domain.contracts import DecisionIntent
from execution_service.domain.risk_result_builder import build_risk_decision_result


def _decision(direction: str) -> DecisionIntent:
    return DecisionIntent.from_dict(
        {
            "decision_id": "dec-rrb-001",
            "exchange": "binance",
            "account_id": "main",
            "symbol": "ETHUSDT",
            "direction_intent": direction,
            "confidence": {"level": "medium", "score": 0.6},
            "cross_horizon_policy": {},
            "risk_hints": {},
        }
    )


def test_risk_result_builder_builds_signal_scope_and_positions() -> None:
    result = build_risk_decision_result(
        decision=_decision("long"),
        account_id="main",
        direction="long",
        position_side="flat",
        allow_dual_side=True,
        long_position_size=0.2,
        short_position_size=0.1,
        step_size=0.1,
        risk_checks=[],
        execution_action="add",
        reject_reason=None,
        applied_risk_rules=[],
        notes="ok",
    )
    signal = result["signal_result"]
    assert signal["scope"]["exchange"] == "binance"
    assert signal["scope"]["account_id"] == "main"
    assert signal["signal_action"] == "add_long"
    assert signal["position_before"]["mode"] == "hedge"
    assert abs(signal["position_after_simulation"]["long_position_size"] - 0.3) < 1e-9
    assert signal["rule_debug"]["hit_rule"] == "none"
    assert isinstance(signal["rule_debug"]["matched_at_ms"], int)
    assert signal["rule_debug"]["matched_at_ms"] > 0
    assert signal["rule_debug"]["evaluation_trace"] == []


def test_risk_result_builder_reduce_short_in_dual_side() -> None:
    result = build_risk_decision_result(
        decision=_decision("long"),
        account_id="main",
        direction="long",
        position_side="long",
        allow_dual_side=True,
        long_position_size=0.2,
        short_position_size=0.4,
        step_size=0.1,
        risk_checks=[],
        execution_action="reduce",
        reject_reason=None,
        applied_risk_rules=["direction_conflict"],
        notes="reduce",
        hit_rule="direction_conflict",
        rule_priority_order=["position_limit", "cooldown"],
        hit_rule_value=1.0,
        hit_rule_threshold=0.0,
        evaluation_trace=[
            {
                "rule": "position_limit",
                "status": "pass",
                "value": 0.2,
                "threshold": 1.0,
                "note_zh": "仓位上限检查(多头): 当前=0.2000, 阈值=1.0000",
            },
            {
                "rule": "direction_conflict",
                "status": "fail",
                "value": 1.0,
                "threshold": 0.5,
                "note_zh": "方向冲突检查: 冲突=1, 不冲突=0, 阈值=0.5",
            },
        ],
    )
    signal = result["signal_result"]
    assert signal["signal_action"] == "reduce_short"
    assert abs(signal["position_after_simulation"]["short_position_size"] - 0.3) < 1e-9
    assert signal["rule_debug"]["hit_rule"] == "direction_conflict"
    assert isinstance(signal["rule_debug"]["matched_at_ms"], int)
    assert len(signal["rule_debug"]["evaluation_trace"]) == 2
