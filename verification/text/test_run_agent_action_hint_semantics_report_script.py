from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_action_hint_semantics_report.sh"


def test_run_agent_action_hint_semantics_report_help() -> None:
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
    assert "agent_action_hint" in out


def test_run_agent_action_hint_semantics_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "action_hint_report.json"
    rows = [
        {
            "ts_ms": 1710000002001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "accept", "direction": "long"}},
        },
        {
            "ts_ms": 1710000002002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "reject", "direction": "long"}},
        },
        {
            "ts_ms": 1710000002003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "accept", "direction": "none"}},
        },
        {
            "ts_ms": 1710000002004,
            "record_type": "agent_output",
            "event_id": "evt-nonminimal",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "deprecated_mode"}, "signal_verdict": {"verdict": "accept", "direction": "long"}},
        },
        {
            "ts_ms": 1710000002005,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "execution_decider",
            "payload": {"risk_hints": {"agent_action_hint": "add"}},
        },
        {
            "ts_ms": 1710000002006,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "execution_decider",
            "payload": {"risk_hints": {"agent_action_hint": "add"}},
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
    assert report["schema_version"] == "agent-action-hint-semantics-report-v1"
    assert summary["decision_trace_record_count"] == 4
    assert summary["execution_decider_record_count"] == 2
    assert summary["minimal_decision_count"] == 3
    assert summary["expected_add_count"] == 1
    assert summary["expected_hold_count"] == 2
    assert summary["actual_hint_available_count"] == 2
    assert summary["missing_actual_hint_count"] == 1
    assert summary["match_count"] == 1
    assert summary["mismatch_count"] == 1
    assert summary["match_ratio_on_available"] == 0.5
    samples = list(report["mismatch_or_missing_samples"])
    assert samples
