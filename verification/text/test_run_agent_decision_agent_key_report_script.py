from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_decision_agent_key_report.sh"


def test_run_agent_decision_agent_key_report_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--input <path>" in out
    assert "--output <path>" in out
    assert "routing.decision_agent_key" in out


def test_run_agent_decision_agent_key_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "agent_key_report.json"
    rows = [
        {
            "ts_ms": 1710000001001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "technical"}},
        },
        {
            "ts_ms": 1710000001002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "onchain"}},
        },
        {
            "ts_ms": 1710000001003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "liquidation"}},
        },
        {
            "ts_ms": 1710000001004,
            "record_type": "agent_output",
            "event_id": "evt-4",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "social_news"}},
        },
        {
            "ts_ms": 1710000001005,
            "record_type": "agent_output",
            "event_id": "evt-5",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "generic"}},
        },
        {
            "ts_ms": 1710000001006,
            "record_type": "agent_output",
            "event_id": "evt-6",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "custom_agent"}},
        },
        {
            "ts_ms": 1710000001007,
            "record_type": "agent_output",
            "event_id": "evt-7",
            "agent_name": "decision_trace",
            "payload": {"routing": {}},
        },
        {
            "ts_ms": 1710000001008,
            "record_type": "agent_output",
            "event_id": "evt-8",
            "agent_name": "other_agent",
            "payload": {"routing": {"decision_agent_key": "technical"}},
        },
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--output", str(out_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_path.exists()

    report = json.loads(out_path.read_text(encoding="utf-8"))
    summary = dict(report["summary"])
    assert report["schema_version"] == "agent-decision-agent-key-report-v1"
    assert summary["decision_trace_record_count"] == 7
    assert summary["decision_trace_event_count"] == 7
    assert summary["technical_count"] == 1
    assert summary["onchain_count"] == 1
    assert summary["liquidation_count"] == 1
    assert summary["social_news_count"] == 1
    assert summary["generic_count"] == 1
    assert summary["unknown_count"] == 2
    assert summary["unknown_ratio"] == 0.285714
    assert summary["core_four_coverage_ratio"] == 0.571429
    top_unknown = list(report["top_unknown_agent_keys"])
    assert top_unknown
    top_keys = {str(x["decision_agent_key"]) for x in top_unknown}
    assert "custom_agent" in top_keys
    assert "missing" in top_keys
