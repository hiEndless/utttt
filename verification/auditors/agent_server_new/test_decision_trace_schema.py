import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _validate(schema: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    def check(node: Dict[str, Any], value: Any) -> bool:
        node_type = node.get("type")
        if node_type == "object" and not isinstance(value, dict):
            return False
        if node_type == "string" and not isinstance(value, str):
            return False
        if node_type == "integer" and not (isinstance(value, int) and not isinstance(value, bool)):
            return False
        if node_type == "array" and not isinstance(value, list):
            return False
        if "const" in node and value != node["const"]:
            return False
        if "enum" in node and value not in node["enum"]:
            return False

        if isinstance(value, dict):
            required = list(node.get("required") or [])
            for k in required:
                if k not in value:
                    return False
            props = dict(node.get("properties") or {})
            for k, v in value.items():
                if k in props:
                    if not check(dict(props[k] or {}), v):
                        return False
                elif node.get("additionalProperties") is False:
                    return False

        if isinstance(value, list):
            item_schema = dict(node.get("items") or {})
            if item_schema:
                for item in value:
                    if not check(item_schema, item):
                        return False

        one_of = node.get("oneOf")
        if isinstance(one_of, list):
            matches = 0
            for candidate in one_of:
                if check(dict(candidate or {}), value):
                    matches += 1
            return matches == 1
        return True

    return check(schema, payload)


def _sample_decision_trace() -> Dict[str, Any]:
    return {
        "event_id": "evt-001",
        "exchange": "binance",
        "symbol": "ETHUSDT",
        "ts": 1710000000000,
        "event": {"event_type": "indicator_signal"},
        "msl": {"summary": "ok"},
        "key_features": {"features": []},
        "evidence": {},
        "anomalies": {},
        "signal_verdict": {"verdict": "accept"},
        "routing": {
            "decision_agent_key": "technical",
            "decision_mode": "rule",
            "llm_parse_status": "rule_only",
            "llm_contract_error_code": "",
            "llm_contract_errors": [],
            "router_config_source": "default:services/agent_server_new/config/signal_router_profiles.json",
            "router_config_version": "abc123",
        },
        "intent": {"intent": "increase"},
        "rule_plan": {"sizing": {"mode": "ratio"}},
        "strategy_gate_result": {"allowed": True},
        "risk_gate": {"global_regime": "normal"},
        "execution_plan": {"action": "add"},
        "llm_observation": {
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content_hash": "079427752e7cf6fb3996ff1a8fce9e916cf5d8357a793e422bef87f0921a1101",
        },
        "memory_metrics": {"memory_hit": False},
        "contract_warnings": [],
        "alert_codes": [],
        "tags": ["decision_trace"],
    }


def test_decision_trace_schema_samples() -> None:
    schema_path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "decision_trace.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    ok = _sample_decision_trace()
    assert _validate(schema, ok)

    bad_missing = _sample_decision_trace()
    bad_missing["llm_observation"].pop("status")
    assert not _validate(schema, bad_missing)

    bad_status = _sample_decision_trace()
    bad_status["llm_observation"]["status"] = "unknown"
    assert not _validate(schema, bad_status)
