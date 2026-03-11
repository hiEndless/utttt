import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.reconcile_codes import RECONCILE_REASON_CODES


def _enum_from_node(node: dict, *, depth: int = 0) -> tuple[str, ...]:
    assert depth < 5, "reason_code 枚举解析层级过深"
    direct = tuple((node or {}).get("enum") or [])
    if direct:
        return direct
    ref = str((node or {}).get("$ref") or "").strip()
    assert ref, "reason_code 节点缺少 enum/$ref"
    rel, _, path = ref.partition("#")
    assert rel and path, "reason_code.$ref 必须包含相对路径与 JSON Pointer"
    ref_schema = json.loads((PROJECT_ROOT / "execution_service" / "docs" / rel).read_text(encoding="utf-8"))
    ref_node = ref_schema
    for part in path.lstrip("/").split("/"):
        ref_node = ref_node[part]
    return _enum_from_node(dict(ref_node or {}), depth=depth + 1)


def test_reconcile_reason_codes_match_schema_enum() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    reason_node = dict(schema.get("properties", {}).get("reason_code") or {})
    enum_values = _enum_from_node(reason_node)
    assert enum_values
    assert set(enum_values) == set(RECONCILE_REASON_CODES)
