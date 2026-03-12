import re
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.observability.decision_trace import DecisionTrace


def _build_trace(*, llm_observation):  # noqa: ANN001
    return DecisionTrace(
        event_id="evt-1",
        exchange="binance",
        symbol="ETHUSDT",
        ts=123,
        event={},
        msl={},
        key_features={},
        evidence={},
        anomalies={},
        signal_verdict={},
        intent={},
        rule_plan={},
        strategy_gate_result={},
        risk_gate={},
        execution_plan={},
        llm_observation=dict(llm_observation),
        memory_metrics={},
        contract_warnings=[],
        alert_codes=[],
        tags=["decision_trace"],
    )


def test_decision_trace_llm_observation_contract_required_keys():
    trace = _build_trace(
        llm_observation={
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content_hash": "a" * 64,
        }
    ).to_dict()
    obs = dict(trace.get("llm_observation") or {})
    assert set(["status", "provider", "model", "raw_content_hash"]).issubset(set(obs.keys()))


def test_decision_trace_llm_observation_status_enum():
    allowed = {"disabled", "ok", "error"}
    for status in allowed:
        trace = _build_trace(
            llm_observation={
                "status": status,
                "provider": "",
                "model": "",
                "raw_content_hash": "",
            }
        ).to_dict()
        assert str(trace.get("llm_observation", {}).get("status")) in allowed


def test_decision_trace_llm_observation_raw_content_hash_semantics():
    hash64 = "079427752e7cf6fb3996ff1a8fce9e916cf5d8357a793e422bef87f0921a1101"
    trace = _build_trace(
        llm_observation={
            "status": "ok",
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "raw_content_hash": hash64,
        }
    ).to_dict()
    obs = dict(trace.get("llm_observation") or {})
    val = str(obs.get("raw_content_hash") or "")
    assert bool(re.fullmatch(r"[0-9a-f]{64}", val))
