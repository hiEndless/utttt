from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.domain.contracts import DecisionIntent
from execution_service.domain.decision_engine import ExecutionDecisionEngine


def _decision(direction: str) -> DecisionIntent:
    return DecisionIntent.from_dict(
        {
            "decision_id": "dec-001",
            "exchange": "binance",
            "symbol": "ETHUSDT",
            "direction_intent": direction,
            "confidence": {"level": "medium", "score": 0.6},
            "cross_horizon_policy": {},
            "risk_hints": {},
        }
    )


def test_rule_priority_position_limit_first() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "long",
            "position_size": 1.0,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 30,
        },
        account_state={"current_drawdown_ratio": 0.2, "max_drawdown_ratio": 0.1},
        risk_policy={},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "position_limit_reached"
    assert isinstance(result.signal_result, dict)
    assert result.signal_result["signal_action"] == "skip"
    assert isinstance(result.signal_result["risk_checks"], list)


def test_rule_priority_cooldown_second() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "position_size": 0.2,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 10,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.1},
        risk_policy={},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "cooldown_active"


def test_rule_priority_drawdown_third() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "position_size": 0.2,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.12, "max_drawdown_ratio": 0.1},
        risk_policy={},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "max_drawdown_exceeded"


def test_rule_priority_direction_conflict_fourth() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("short"),
        position_state={
            "position_side": "long",
            "position_size": 0.3,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.1},
        risk_policy={},
    )
    assert result.execution_action == "reduce"
    assert result.reject_reason == "direction_conflict_with_position"
    assert isinstance(result.signal_result, dict)
    assert result.signal_result["signal_action"] == "reduce_long"
    checks = result.signal_result["risk_checks"]
    assert any(c["check"] == "short_leg_position_limit" for c in checks)


def test_allow_add_when_all_rules_pass() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "position_size": 0.1,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.1},
        risk_policy={},
    )
    assert result.execution_action == "add"
    assert result.reject_reason is None
    assert isinstance(result.signal_result, dict)
    assert result.signal_result["signal_action"] == "add_long"
    checks = result.signal_result["risk_checks"]
    assert any(c["check"] == "account_drawdown_limit" for c in checks)
    assert all(isinstance(c.get("message_zh"), str) and c["message_zh"] for c in checks)
    assert result.signal_result["rule_debug"]["hit_rule"] == "passed_all_rules"
    assert isinstance(result.signal_result["rule_debug"]["evaluation_trace"], list)


def test_dual_side_mode_allows_opposite_direction_add() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("short"),
        position_state={
            "position_mode": "hedge",
            "position_side": "long",
            "position_size": 0.5,
            "long_position_size": 0.5,
            "short_position_size": 0.0,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.1},
        risk_policy={"allow_dual_side": True},
    )
    assert result.execution_action == "add"
    assert result.reject_reason is None
    assert "dual_side_hedge_mode" in result.applied_risk_rules
    assert isinstance(result.signal_result, dict)
    assert result.signal_result["signal_action"] == "add_short"
    assert result.signal_result["position_before"]["long_position_size"] == 0.5
    assert result.signal_result["position_after_simulation"]["short_position_size"] > 0


def test_dual_side_short_leg_limit_blocks_short_add() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("short"),
        position_state={
            "position_mode": "hedge",
            "long_position_size": 0.3,
            "short_position_size": 0.8,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.1},
        risk_policy={"allow_dual_side": True, "max_short_position_size": 0.8},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "position_limit_reached"


def test_account_risk_checks_show_failure_when_balance_too_low() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "position_size": 0.1,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 0,
        },
        account_state={
            "account_equity": 1000.0,
            "available_balance": 10.0,
            "current_drawdown_ratio": 0.01,
            "max_drawdown_ratio": 0.5,
        },
        risk_policy={
            "min_available_balance": 100.0,
            "max_drawdown_ratio": 0.5,
        },
    )
    assert isinstance(result.signal_result, dict)
    checks = result.signal_result["risk_checks"]
    bal_check = next(c for c in checks if c["check"] == "account_available_balance")
    assert bal_check["status"] == "fail"
    assert "可用余额检查" in bal_check["message_zh"]


def test_custom_rule_priority_order_can_override_default() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "long",
            "position_size": 1.0,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 5,
        },
        account_state={"current_drawdown_ratio": 0.3, "max_drawdown_ratio": 0.1},
        risk_policy={
            "rule_priority_order": [
                "max_drawdown",
                "position_limit",
                "cooldown",
                "account_notional",
                "margin_ratio",
                "daily_loss",
                "consecutive_loss",
                "direction_conflict",
            ]
        },
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "max_drawdown_exceeded"


def test_invalid_custom_rule_priority_order_falls_back_to_default() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "long",
            "position_size": 1.0,
            "max_position_size": 1.0,
            "cooldown_seconds_left": 5,
        },
        account_state={"current_drawdown_ratio": 0.3, "max_drawdown_ratio": 0.1},
        risk_policy={"rule_priority_order": ["max_drawdown"]},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "position_limit_reached"


def test_account_notional_rule_rejects_when_exceeded() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "long_position_size": 0.2,
            "short_position_size": 0.1,
            "gross_notional": 20000.0,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.5, "margin_ratio": 0.1},
        risk_policy={"max_account_notional": 10000.0, "max_margin_ratio": 0.8},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "account_notional_exceeded"


def test_margin_ratio_rule_rejects_when_exceeded() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "long_position_size": 0.2,
            "short_position_size": 0.1,
            "cooldown_seconds_left": 0,
        },
        account_state={"current_drawdown_ratio": 0.01, "max_drawdown_ratio": 0.5, "margin_ratio": 0.9},
        risk_policy={"max_account_notional": 100000.0, "max_margin_ratio": 0.5},
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "account_margin_ratio_exceeded"


def test_daily_loss_rule_rejects_when_exceeded() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "long_position_size": 0.2,
            "short_position_size": 0.1,
            "cooldown_seconds_left": 0,
        },
        account_state={
            "current_drawdown_ratio": 0.01,
            "max_drawdown_ratio": 0.5,
            "margin_ratio": 0.1,
            "daily_loss": 300.0,
            "consecutive_loss_count": 1,
        },
        risk_policy={
            "max_account_notional": 100000.0,
            "max_margin_ratio": 0.8,
            "max_daily_loss": 200.0,
            "max_consecutive_loss_count": 5,
        },
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "daily_loss_exceeded"
    assert result.signal_result["rule_debug"]["hit_rule"] == "daily_loss"


def test_consecutive_loss_rule_rejects_when_exceeded() -> None:
    result = ExecutionDecisionEngine.decide(
        _decision("long"),
        position_state={
            "position_side": "flat",
            "long_position_size": 0.2,
            "short_position_size": 0.1,
            "cooldown_seconds_left": 0,
        },
        account_state={
            "current_drawdown_ratio": 0.01,
            "max_drawdown_ratio": 0.5,
            "margin_ratio": 0.1,
            "daily_loss": 100.0,
            "consecutive_loss_count": 4,
        },
        risk_policy={
            "max_account_notional": 100000.0,
            "max_margin_ratio": 0.8,
            "max_daily_loss": 200.0,
            "max_consecutive_loss_count": 3,
        },
    )
    assert result.execution_action == "skip"
    assert result.reject_reason == "consecutive_loss_exceeded"
    assert result.signal_result["rule_debug"]["hit_rule"] == "consecutive_loss"
