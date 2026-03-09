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
