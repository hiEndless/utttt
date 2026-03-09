import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution_service.version import SCHEMA_MAPPING_VERSION


def test_schema_mapping_manifest_is_valid() -> None:
    mapping_path = PROJECT_ROOT / "execution_service" / "docs" / "schema_mapping.json"
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    assert data.get("version") == SCHEMA_MAPPING_VERSION
    items = data.get("items")
    assert isinstance(items, list) and items

    for item in items:
        assert isinstance(item, dict)
        name = str(item.get("name") or "").strip()
        schema_rel = str(item.get("schema") or "").strip()
        code_rel = str(item.get("code") or "").strip()
        symbol = str(item.get("symbol") or "").strip()
        owner = str(item.get("owner") or "").strip()
        change_policy = str(item.get("change_policy") or "").strip()
        fields = item.get("fields")

        assert name
        assert owner
        assert change_policy in {"breaking", "non_breaking"}
        assert schema_rel
        assert code_rel
        assert symbol
        assert isinstance(fields, list) and fields

        schema_path = PROJECT_ROOT / schema_rel
        code_path = PROJECT_ROOT / code_rel
        assert schema_path.is_file(), f"schema not found: {schema_rel}"
        assert code_path.is_file(), f"code not found: {code_rel}"

        code_text = code_path.read_text(encoding="utf-8")
        assert symbol in code_text, f"symbol not found: {symbol} in {code_rel}"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema.get("properties") or {}
        assert isinstance(props, dict)
        for f in fields:
            key = str(f).strip()
            assert key in props, f"field {key} missing in {schema_rel}"
