from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.execution_service.domain.contracts import DecisionIntent, ExecutionResult


def _alt_summary() -> dict:
    return {
        "available_sources": ["news"],
        "unavailable_sources": ["social", "onchain"],
        "provider_states": {"news": "primary", "social": "empty", "onchain": "empty"},
        "data_sources": {"news": "feature_service.news", "social": "", "onchain": ""},
        "inference_sources": {"news": "feature_service.normalizer", "social": "", "onchain": ""},
        "feature_keys": {"news": ["headline_score"], "social": [], "onchain": []},
        "evidence_counts": {"news": 2, "social": 0, "onchain": 0},
    }


def test_decision_intent_v1_parse_success() -> None:
    payload = {
        "decision_id": "dec-001",
        "exchange": "binance",
        "account_id": "sub_1",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
        "risk_hints": {
            "market_fragility": "medium",
            "decision_agent_key": "technical",
            "signal_verdict": "accept",
            "signal_reliability_score": 0.81,
        },
        "trace_id": "trace-001",
    }
    decision = DecisionIntent.from_dict(payload)
    data = decision.to_dict()
    assert data["decision_id"] == "dec-001"
    assert data["account_id"] == "sub_1"
    assert data["direction_intent"] == "long"
    assert data["confidence"]["score"] == 0.66
    assert data["risk_hints"]["decision_agent_key"] == "technical"
    assert data["risk_hints"]["signal_verdict"] == "accept"
    assert data["risk_hints"]["signal_reliability_score"] == 0.81


def test_decision_intent_accepts_valid_alternative_source_summary() -> None:
    payload = {
        "decision_id": "dec-alt-001",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"alternative_source_summary": _alt_summary()},
    }
    decision = DecisionIntent.from_dict(payload)
    data = decision.to_dict()
    assert "alternative_source_summary" in data["risk_hints"]


def test_decision_intent_rejects_invalid_alternative_source_summary_provider_state() -> None:
    bad = _alt_summary()
    bad["provider_states"]["news"] = "mystery"
    payload = {
        "decision_id": "dec-alt-002",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"alternative_source_summary": bad},
    }
    try:
        DecisionIntent.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "alternative_source_summary.provider_states.news" in str(exc)


def test_decision_intent_v1_reject_invalid_direction() -> None:
    payload = {
        "decision_id": "dec-001",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "buy",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
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
        "decision_confidence": {"level": "medium", "score": 0.66},
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


def test_decision_intent_accepts_legacy_confidence_only_with_autofill() -> None:
    payload = {
        "decision_id": "dec-004b",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "short",
        "confidence": {"level": "high", "score": 0.88},
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


def test_decision_intent_rejects_invalid_signal_verdict() -> None:
    payload = {
        "decision_id": "dec-006",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "high", "score": 0.92},
        "cross_horizon_policy": {},
        "risk_hints": {"signal_verdict": "maybe"},
    }
    try:
        DecisionIntent.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "signal_verdict" in str(exc)


def test_decision_intent_rejects_invalid_signal_reliability_score() -> None:
    payload = {
        "decision_id": "dec-007",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"signal_reliability_score": 1.3},
    }
    try:
        DecisionIntent.from_dict(payload)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "signal_reliability_score" in str(exc)


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
