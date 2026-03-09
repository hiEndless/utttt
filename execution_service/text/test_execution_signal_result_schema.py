import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from execution_service.text.schema_utils import validate_payload_with_local_refs


def test_execution_signal_result_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "execution_service" / "docs" / "execution_signal_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    base_dir = Path(PROJECT_ROOT) / "execution_service" / "docs"

    good = {
        "signal_action": "add_long",
        "mode": "simulated",
        "scope": {"exchange": "binance", "account_id": "main", "symbol": "ETHUSDT"},
        "position_before": {
            "mode": "hedge",
            "long_position_size": 0.5,
            "short_position_size": 0.2,
            "net_position_size": 0.3,
        },
        "position_after_simulation": {
            "long_position_size": 0.6,
            "short_position_size": 0.2,
            "net_position_size": 0.4,
        },
    }
    assert validate_payload_with_local_refs(schema, good, base_dir)

    bad = {
        "signal_action": "buy",
        "mode": "simulated",
        "scope": {"exchange": "binance", "account_id": "main", "symbol": "ETHUSDT"},
        "position_before": {
            "mode": "hedge",
            "long_position_size": 0.5,
            "short_position_size": 0.2,
            "net_position_size": 0.3,
        },
        "position_after_simulation": {
            "long_position_size": 0.6,
            "short_position_size": 0.2,
            "net_position_size": 0.4,
        },
    }
    assert not validate_payload_with_local_refs(schema, bad, base_dir)
