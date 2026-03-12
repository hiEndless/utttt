import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_rule_priority_order_ref_used_by_risk_policy_and_rule_debug() -> None:
    policy_schema = _load_schema("execution_service/docs/risk_policy.schema.json")
    rule_debug_schema = _load_schema("execution_service/docs/rule_debug.schema.json")
    ref_expected = "./rule_priority_order.schema.json#/properties/rule_priority_order"
    assert policy_schema.get("properties", {}).get("rule_priority_order", {}).get("$ref", "") == ref_expected
    assert rule_debug_schema.get("properties", {}).get("rule_priority_order", {}).get("$ref", "") == ref_expected


def test_rule_priority_order_enum_and_bounds_frozen() -> None:
    order_schema = _load_schema("execution_service/docs/rule_priority_order.schema.json")
    node = order_schema.get("properties", {}).get("rule_priority_order", {})
    assert node.get("minItems") == 8
    assert node.get("maxItems") == 8
    assert node.get("uniqueItems") is True
    assert node.get("items", {}).get("enum", []) == [
        "position_limit",
        "cooldown",
        "max_drawdown",
        "account_notional",
        "margin_ratio",
        "daily_loss",
        "consecutive_loss",
        "direction_conflict",
    ]

