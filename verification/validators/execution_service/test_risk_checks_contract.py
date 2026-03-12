import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _load_schema(path: str) -> dict:
    schema_path = Path(PROJECT_ROOT) / path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_signal_result_uses_risk_checks_ref() -> None:
    signal_schema = _load_schema("services/execution_service/docs/execution_signal_result.schema.json")
    assert (
        signal_schema.get("properties", {}).get("risk_checks", {}).get("$ref", "")
        == "./risk_checks.schema.json#/properties/risk_checks"
    )


def test_risk_checks_required_fields_frozen() -> None:
    checks_schema = _load_schema("services/execution_service/docs/risk_checks.schema.json")
    required_fields = (
        checks_schema.get("properties", {})
        .get("risk_checks", {})
        .get("items", {})
        .get("required", [])
    )
    assert required_fields == ["check", "scope", "status", "value", "threshold", "message_zh"]

