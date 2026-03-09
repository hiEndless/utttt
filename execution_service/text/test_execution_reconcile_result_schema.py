import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _validate(schema: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    def _type_ok(type_node: Any, value: Any) -> bool:
        if isinstance(type_node, list):
            return any(_type_ok(t, value) for t in type_node)
        if type_node == "object":
            return isinstance(value, dict)
        if type_node == "string":
            return isinstance(value, str)
        if type_node == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if type_node == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if type_node == "null":
            return value is None
        return True

    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type is not None and not _type_ok(node_type, value):
            return False
        if "enum" in node and value not in node["enum"]:
            return False
        if isinstance(value, str):
            min_len = node.get("minLength")
            if isinstance(min_len, int) and len(value) < min_len:
                return False
        if isinstance(value, int):
            minimum = node.get("minimum")
            if isinstance(minimum, int) and value < minimum:
                return False
        if isinstance(value, dict):
            required = list(node.get("required") or [])
            for k in required:
                if k not in value:
                    return False
            props = dict(node.get("properties") or {})
            for k, v in value.items():
                if k in props and not check(dict(props[k] or {}), v):
                    return False
        return True

    return check(schema, payload)


def test_execution_reconcile_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good_mock = {
        "mode": "mock",
        "venue": "mock_exchange",
        "order_id": "mock-order-001",
        "decision_id": "dec-001",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "status": "filled",
        "filled_qty": 1.0,
        "avg_price": 1000.0,
        "idempotency_hit": False,
        "ts": 1760000000000,
    }
    assert _validate(schema, good_mock)

    good_exchange = {
        "mode": "exchange_skeleton",
        "venue": "binance",
        "order_id": "binance-ord-001",
        "decision_id": "dec-002",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "status": "submitted",
        "filled_qty": 0.0,
        "avg_price": None,
        "note": "占位",
        "idempotency_hit": True,
        "ts": 1760000000001,
    }
    assert _validate(schema, good_exchange)

    bad = {
        "mode": "mock",
        "order_id": "",
        "status": "open",
        "ts": 1760000000000,
    }
    assert not _validate(schema, bad)
