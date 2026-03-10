import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_decision_intent_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "decision_intent.schema.json"
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
        "risk_hints": {"market_fragility": "medium"},
        "trace_id": "trace-001"
    }
    assert validate_payload_with_local_refs(
        schema, good, Path(PROJECT_ROOT) / "execution_service" / "docs"
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
        schema, bad, Path(PROJECT_ROOT) / "execution_service" / "docs"
    )
