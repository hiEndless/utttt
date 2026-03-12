import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.execution_service.domain.risk_check_codes import RISK_CHECK_CODES


def test_risk_check_codes_match_signal_result_schema_enum() -> None:
    schema_path = PROJECT_ROOT / "services" / "execution_service" / "docs" / "risk_checks.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum_values = (
        schema.get("properties", {})
        .get("risk_checks", {})
        .get("items", {})
        .get("properties", {})
        .get("check", {})
        .get("enum", [])
    )
    assert enum_values
    assert set(enum_values) == set(RISK_CHECK_CODES)
