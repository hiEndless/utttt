import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
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
    rule_debug_schema = _load_schema("execution_service/docs/rule_debug.schema.json")
    reason_schema = _load_schema("execution_service/docs/risk_state_change_reason.schema.json")
    signal_rule_debug_ref = signal_schema.get("properties", {}).get("rule_debug", {}).get("$ref", "")
    decision_rule_debug_ref = decision_schema.get("properties", {}).get("rule_debug", {}).get("$ref", "")
    signal_ref = (
        rule_debug_schema.get("properties", {})
        .get("risk_state_change_reason", {})
        .get("$ref", "")
    )
    decision_ref = (
        rule_debug_schema.get("properties", {})
        .get("risk_state_change_reason", {})
        .get("$ref", "")
    )
    signal_enum = reason_schema.get("properties", {}).get("reason_code", {}).get("enum", [])
    decision_enum = reason_schema.get("properties", {}).get("reason_code", {}).get("enum", [])
    assert signal_rule_debug_ref == "./rule_debug.schema.json"
    assert decision_rule_debug_ref == "./rule_debug.schema.json"
    assert signal_ref == "./risk_state_change_reason.schema.json#/properties/reason_code"
    assert decision_ref == "./risk_state_change_reason.schema.json#/properties/reason_code"
    assert set(signal_enum) == set(RISK_STATE_CHANGE_REASONS)
    assert set(decision_enum) == set(RISK_STATE_CHANGE_REASONS)


def test_risk_state_change_reason_zh_mapping_complete() -> None:
    signal_schema = _load_schema("execution_service/docs/execution_signal_result.schema.json")
    decision_schema = _load_schema("execution_service/docs/decision_state.schema.json")
    rule_debug_schema = _load_schema("execution_service/docs/rule_debug.schema.json")
    signal_rule_debug_ref = signal_schema.get("properties", {}).get("rule_debug", {}).get("$ref", "")
    decision_rule_debug_ref = decision_schema.get("properties", {}).get("rule_debug", {}).get("$ref", "")
    signal_zh_ref = (
        rule_debug_schema.get("properties", {})
        .get("risk_state_change_reason_zh", {})
        .get("$ref", "")
    )
    decision_zh_ref = (
        rule_debug_schema.get("properties", {})
        .get("risk_state_change_reason_zh", {})
        .get("$ref", "")
    )
    assert signal_rule_debug_ref == "./rule_debug.schema.json"
    assert decision_rule_debug_ref == "./rule_debug.schema.json"
    assert signal_zh_ref == "./risk_state_change_reason.schema.json#/properties/reason_zh"
    assert decision_zh_ref == "./risk_state_change_reason.schema.json#/properties/reason_zh"
    assert set(RISK_STATE_CHANGE_REASON_ZH.keys()) == set(RISK_STATE_CHANGE_REASONS)
    assert all(isinstance(v, str) and v.strip() for v in RISK_STATE_CHANGE_REASON_ZH.values())
