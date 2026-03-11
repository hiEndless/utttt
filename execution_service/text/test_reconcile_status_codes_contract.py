import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.reconcile_statuses import RECONCILE_STATUSES


def _enum_from_status_node(status_node: dict) -> tuple[str, ...]:
    direct = tuple(status_node.get("enum") or [])
    if direct:
        return direct
    ref = str(status_node.get("$ref") or "").strip()
    assert ref, "status 节点缺少 enum/$ref"
    rel, _, path = ref.partition("#")
    assert rel and path, "status.$ref 必须包含相对路径与 JSON Pointer"
    ref_schema = json.loads((PROJECT_ROOT / "execution_service" / "docs" / rel).read_text(encoding="utf-8"))
    node = ref_schema
    for part in path.lstrip("/").split("/"):
        node = node[part]
    return tuple((node or {}).get("enum") or [])


def test_reconcile_status_codes_match_schema_enum() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    status_node = dict(schema.get("properties", {}).get("status") or {})
    enum_values = _enum_from_status_node(status_node)
    assert enum_values
    assert set(enum_values) == set(RECONCILE_STATUSES)
