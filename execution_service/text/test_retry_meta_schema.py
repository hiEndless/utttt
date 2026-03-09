import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.domain.retry_meta import RETRY_META_STATUSES


def _enum_from(schema: dict, path: list[str]) -> tuple[str, ...]:
    node = schema
    for key in path:
        node = dict(node.get(key) or {})
    return tuple(node.get("enum") or [])


def test_retry_meta_schema_enum_matches_constants() -> None:
    schema_path = PROJECT_ROOT / "execution_service" / "docs" / "retry_meta.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum_values = _enum_from(schema, ["properties", "status"])
    assert enum_values
    assert set(enum_values) == set(RETRY_META_STATUSES)


def test_retry_meta_schema_enum_matches_main_schemas() -> None:
    retry_meta_schema = json.loads(
        (PROJECT_ROOT / "execution_service" / "docs" / "retry_meta.schema.json").read_text(encoding="utf-8")
    )
    result_schema = json.loads(
        (PROJECT_ROOT / "execution_service" / "docs" / "execution_result.schema.json").read_text(encoding="utf-8")
    )
    reconcile_schema = json.loads(
        (PROJECT_ROOT / "execution_service" / "docs" / "execution_reconcile_result.schema.json").read_text(
            encoding="utf-8"
        )
    )

    source_enum = _enum_from(retry_meta_schema, ["properties", "status"])
    result_ref = (
        result_schema
        .get("properties", {})
        .get("order_result", {})
        .get("properties", {})
        .get("retry_meta", {})
        .get("$ref")
    )
    reconcile_ref = reconcile_schema.get("properties", {}).get("retry_meta", {}).get("$ref")

    assert result_ref == "./retry_meta.schema.json"
    assert reconcile_ref == "./retry_meta.schema.json"
    assert source_enum
