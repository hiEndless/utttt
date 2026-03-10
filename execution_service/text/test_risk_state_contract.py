import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.domain.risk_states import RISK_STATES


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_risk_state_enum_matches_signal_and_decision_schema() -> None:
    signal_schema = _load_schema("execution_service/docs/execution_signal_result.schema.json")
    decision_schema = _load_schema("execution_service/docs/decision_state.schema.json")
    risk_state_schema = _load_schema("execution_service/docs/risk_state.schema.json")
    signal_ref = signal_schema.get("properties", {}).get("risk_state", {}).get("$ref", "")
    decision_ref = decision_schema.get("properties", {}).get("risk_state", {}).get("$ref", "")
    signal_enum = risk_state_schema.get("properties", {}).get("risk_state", {}).get("enum", [])
    decision_enum = risk_state_schema.get("properties", {}).get("risk_state", {}).get("enum", [])
    assert signal_ref == "./risk_state.schema.json#/properties/risk_state"
    assert decision_ref == "./risk_state.schema.json#/properties/risk_state"
    assert set(signal_enum) == set(RISK_STATES)
    assert set(decision_enum) == set(RISK_STATES)
