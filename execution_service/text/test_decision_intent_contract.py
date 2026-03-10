from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service.domain.contracts import DecisionIntent, ExecutionResult


def test_decision_intent_v1_parse_success() -> None:
    payload = {
        "decision_id": "dec-001",
        "exchange": "binance",
        "account_id": "sub_1",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
        "risk_hints": {"market_fragility": "medium"},
        "trace_id": "trace-001",
    }
    decision = DecisionIntent.from_dict(payload)
    data = decision.to_dict()
    assert data["decision_id"] == "dec-001"
    assert data["account_id"] == "sub_1"
    assert data["direction_intent"] == "long"
    assert data["confidence"]["score"] == 0.66


def test_decision_intent_v1_reject_invalid_direction() -> None:
    payload = {
        "decision_id": "dec-001",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "buy",
        "confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {},
    }
    try:
        DecisionIntent.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "direction_intent" in str(exc)


def test_decision_intent_default_account_id_main() -> None:
    payload = {
        "decision_id": "dec-003",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {},
    }
    decision = DecisionIntent.from_dict(payload)
    assert decision.account_id == "main"


def test_decision_intent_accepts_decision_confidence_alias() -> None:
    payload = {
        "decision_id": "dec-004",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "short",
        "decision_confidence": {"level": "high", "score": 0.88},
        "cross_horizon_policy": {},
        "risk_hints": {},
    }
    decision = DecisionIntent.from_dict(payload)
    data = decision.to_dict()
    assert data["confidence"] == {"level": "high", "score": 0.88}
    assert data["decision_confidence"] == {"level": "high", "score": 0.88}


def test_decision_intent_rejects_confidence_mismatch() -> None:
    payload = {
        "decision_id": "dec-005",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "low", "score": 0.21},
        "decision_confidence": {"level": "high", "score": 0.92},
        "cross_horizon_policy": {},
        "risk_hints": {},
    }
    try:
        DecisionIntent.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "不一致" in str(exc)


def test_execution_result_v1_parse_success() -> None:
    payload = {
        "decision_id": "dec-001",
        "execution_action": "hold",
        "reject_reason": "position_limit_reached",
        "applied_risk_rules": ["max_position_limit"],
        "notes": "当前仓位已达上限",
    }
    result = ExecutionResult.from_dict(payload)
    data = result.to_dict()
    assert data["execution_action"] == "hold"
    assert data["reject_reason"] == "position_limit_reached"


def test_execution_result_v1_reject_invalid_action() -> None:
    payload = {
        "decision_id": "dec-001",
        "execution_action": "open",
        "applied_risk_rules": [],
    }
    try:
        ExecutionResult.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "execution_action" in str(exc)
