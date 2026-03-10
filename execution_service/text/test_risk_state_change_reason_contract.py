import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.domain.risk_state_change_reasons import (
    RISK_STATE_CHANGE_REASONS,
    RISK_STATE_CHANGE_REASON_ZH,
)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_risk_state_change_reason_enum_matches_schemas() -> None:
    signal_schema = _load_schema("execution_service/docs/execution_signal_result.schema.json")
    decision_schema = _load_schema("execution_service/docs/decision_state.schema.json")
    signal_enum = (
        signal_schema.get("properties", {})
        .get("rule_debug", {})
        .get("properties", {})
        .get("risk_state_change_reason", {})
        .get("enum", [])
    )
    decision_enum = (
        decision_schema.get("properties", {})
        .get("rule_debug", {})
        .get("properties", {})
        .get("risk_state_change_reason", {})
        .get("enum", [])
    )
    assert set(signal_enum) == set(RISK_STATE_CHANGE_REASONS)
    assert set(decision_enum) == set(RISK_STATE_CHANGE_REASONS)


def test_risk_state_change_reason_zh_mapping_complete() -> None:
    assert set(RISK_STATE_CHANGE_REASON_ZH.keys()) == set(RISK_STATE_CHANGE_REASONS)
    assert all(isinstance(v, str) and v.strip() for v in RISK_STATE_CHANGE_REASON_ZH.values())

