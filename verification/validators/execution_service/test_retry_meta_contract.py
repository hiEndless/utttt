import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.retry_meta import RETRY_META_STATUSES


def _retry_meta_status_enum_from_ref_node(ref_node: dict) -> tuple[str, ...]:
    ref = str(ref_node.get("$ref") or "")
    assert ref, "retry_meta 节点缺少 $ref"
    schema_path = (PROJECT_ROOT / "services" / "execution_service" / "docs" / ref).resolve()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status_node = dict(schema.get("properties", {}).get("status") or {})
    return tuple(status_node.get("enum") or [])


def test_retry_meta_status_matches_reconcile_schema() -> None:
    schema_path = PROJECT_ROOT / "services" / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ref_node = dict(schema.get("properties", {}).get("retry_meta") or {})
    enum_values = _retry_meta_status_enum_from_ref_node(ref_node)
    assert enum_values
    assert set(enum_values) == set(RETRY_META_STATUSES)


def test_retry_meta_status_matches_execution_result_schema() -> None:
    schema_path = PROJECT_ROOT / "services" / "execution_service" / "docs" / "execution_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ref_node = (
        dict(schema.get("properties", {}).get("order_result") or {})
        .get("properties", {})
        .get("retry_meta", {})
    )
    enum_values = _retry_meta_status_enum_from_ref_node(ref_node)
    assert enum_values
    assert set(enum_values) == set(RETRY_META_STATUSES)
