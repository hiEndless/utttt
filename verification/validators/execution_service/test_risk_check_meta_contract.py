import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.risk_check_meta import RISK_CHECK_SCOPES, RISK_CHECK_STATUSES


def test_risk_check_scopes_and_statuses_match_signal_result_schema_enum() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "risk_checks.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    item_props = (
        schema.get("properties", {})
        .get("risk_checks", {})
        .get("items", {})
        .get("properties", {})
    )
    scope_enum = item_props.get("scope", {}).get("enum", [])
    status_enum = item_props.get("status", {}).get("enum", [])
    assert set(scope_enum) == set(RISK_CHECK_SCOPES)
    assert set(status_enum) == set(RISK_CHECK_STATUSES)
