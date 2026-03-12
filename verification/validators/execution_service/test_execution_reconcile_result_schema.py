import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from verification.validators.execution_service.schema_utils import validate_payload_with_local_refs


def test_execution_reconcile_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "execution_service" / "docs" / "execution_reconcile_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    good_exchange_filled = {
        "mode": "exchange",
        "sink_mode": "exchange",
        "venue": "binance",
        "order_id": "mock-order-001",
        "decision_id": "dec-001",
        "account_id": "main",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "status": "filled",
        "status_source": "execution_sink",
        "reconcile_status": "filled",
        "reconcile_status_source": "execution_sink",
        "filled_qty": 1.0,
        "avg_price": 1000.0,
        "idempotency_hit": False,
        "retry_meta": {"attempts": 1, "max_retries": 0, "status": "ok"},
        "ts": 1760000000000,
    }
    assert validate_payload_with_local_refs(
        schema, good_exchange_filled, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )

    good_exchange = {
        "mode": "exchange",
        "sink_mode": "exchange",
        "venue": "binance",
        "order_id": "binance-ord-001",
        "decision_id": "dec-002",
        "account_id": "main",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "status": "submitted",
        "status_source": "execution_sink",
        "reconcile_status": "submitted",
        "reconcile_status_source": "execution_sink",
        "filled_qty": 0.0,
        "avg_price": None,
        "note": "占位",
        "request": {
            "symbol": "ETHUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.001000",
            "newClientOrderId": "exec-dec-002-a1b2c3",
        },
        "exchange_raw": {"status": "NEW"},
        "idempotency_hit": True,
        "retry_meta": {"attempts": 2, "max_retries": 2, "status": "ok"},
        "ts": 1760000000001,
    }
    assert validate_payload_with_local_refs(
        schema, good_exchange, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )

    good_failed = {
        "mode": "exchange",
        "sink_mode": "exchange",
        "order_id": "mock-order-err-001",
        "account_id": "main",
        "status": "failed",
        "status_source": "execution_service",
        "reconcile_status": "failed",
        "reconcile_status_source": "execution_service",
        "reason_code": "reconcile_non_retryable_error",
        "error_message": "invalid_order_id",
        "idempotency_hit": False,
        "retry_meta": {"attempts": 1, "max_retries": 3, "status": "failed", "retryable": False},
        "ts": 1760000000002,
    }
    assert validate_payload_with_local_refs(
        schema, good_failed, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )

    good_in_progress = {
        "mode": "exchange",
        "sink_mode": "exchange",
        "order_id": "mock-order-inprogress-001",
        "status": "submitted",
        "status_source": "execution_service",
        "reconcile_status": "submitted",
        "reconcile_status_source": "execution_service",
        "reason_code": "reconcile_in_progress",
        "idempotency_hit": False,
        "ts": 1760000000003,
    }
    assert validate_payload_with_local_refs(
        schema, good_in_progress, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )

    bad = {
        "mode": "exchange",
        "order_id": "",
        "status": "open",
        "ts": 1760000000000,
    }
    assert not validate_payload_with_local_refs(
        schema, bad, Path(PROJECT_ROOT) / "services" / "execution_service" / "docs"
    )
