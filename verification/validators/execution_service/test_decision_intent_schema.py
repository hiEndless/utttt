import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from verification.validators.execution_service.schema_utils import validate_payload_with_local_refs


def test_decision_intent_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good = {
        "decision_id": "dec-001",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {"suggested_policy": "reduce_risk"},
        "risk_hints": {
            "market_fragility": "medium",
            "decision_agent_key": "technical",
            "decision_mode": "rule",
            "llm_parse_status": "rule_only",
            "prompt_config_source": "default:services/agent_server_new/config/signal_decision_prompt_profiles.json",
            "prompt_config_version": "f00dbabe1234abcd",
            "signal_verdict": "accept",
            "signal_reliability_score": 0.83,
            "alternative_source_summary": {
                "available_sources": ["news"],
                "unavailable_sources": ["social", "onchain"],
                "provider_states": {"news": "primary", "social": "empty", "onchain": "empty"},
                "data_sources": {"news": "feature_service.news", "social": "", "onchain": ""},
                "inference_sources": {"news": "feature_service.normalizer", "social": "", "onchain": ""},
                "feature_keys": {"news": ["headline_score"], "social": [], "onchain": []},
                "evidence_counts": {"news": 1, "social": 0, "onchain": 0}
            }
        },
        "trace_id": "trace-001"
    }
    assert validate_payload_with_local_refs(
        schema, good, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )

    bad = {
        "decision_id": "dec-002",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "buy",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {}
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_invalid_signal_verdict() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-004",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"signal_verdict": "maybe"},
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_invalid_signal_reliability_score() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-005",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"signal_reliability_score": 1.2},
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_invalid_decision_mode() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-005b",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"decision_mode": "hybrid"},
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_invalid_llm_parse_status() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-005c",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"llm_parse_status": "unknown_status"},
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_empty_prompt_config_source() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-005d",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {"prompt_config_source": ""},
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )


def test_decision_intent_schema_rejects_invalid_alternative_source_summary() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "decision_intent.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    bad = {
        "decision_id": "dec-003",
        "exchange": "binance",
        "account_id": "main",
        "symbol": "ETHUSDT",
        "direction_intent": "long",
        "confidence": {"level": "medium", "score": 0.66},
        "decision_confidence": {"level": "medium", "score": 0.66},
        "cross_horizon_policy": {},
        "risk_hints": {
            "alternative_source_summary": {
                "available_sources": ["news"],
                "unavailable_sources": ["social", "onchain"],
                "provider_states": {"news": "unknown", "social": "empty", "onchain": "empty"},
                "data_sources": {"news": "feature_service.news", "social": "", "onchain": ""},
                "inference_sources": {"news": "feature_service.normalizer", "social": "", "onchain": ""},
                "feature_keys": {"news": ["headline_score"], "social": [], "onchain": []},
                "evidence_counts": {"news": 1, "social": 0, "onchain": 0}
            }
        }
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )
