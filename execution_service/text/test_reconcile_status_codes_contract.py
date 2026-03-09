import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.reconcile_statuses import RECONCILE_STATUSES


def test_reconcile_status_codes_match_schema_enum() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status_node = dict(schema.get("properties", {}).get("status") or {})
    enum_values = tuple(status_node.get("enum") or [])
    assert enum_values
    assert set(enum_values) == set(RECONCILE_STATUSES)
