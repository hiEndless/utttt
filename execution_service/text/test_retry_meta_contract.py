import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.retry_meta import RETRY_META_STATUSES


def test_retry_meta_status_matches_reconcile_schema() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status_node = (
        dict(schema.get("properties", {}).get("retry_meta") or {}).get("properties", {}).get("status") or {}
    )
    enum_values = tuple(status_node.get("enum") or [])
    assert enum_values
    assert set(enum_values) == set(RETRY_META_STATUSES)


def test_retry_meta_status_matches_execution_result_schema() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "execution_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status_node = (
        dict(schema.get("properties", {}).get("order_result") or {})
        .get("properties", {})
        .get("retry_meta", {})
        .get("properties", {})
        .get("status", {})
    )
    enum_values = tuple(status_node.get("enum") or [])
    assert enum_values
    assert set(enum_values) == set(RETRY_META_STATUSES)
