from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_execution_direction_intent_report.sh"


def test_run_agent_execution_direction_intent_report_help() -> None:
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
    assert "--limit <n>" in out


def test_run_agent_execution_direction_intent_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "agent_execution_direction_intent_report.json"
    rows = [
        {
            "ts_ms": 1710000000001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "execution_decider_request",
            "payload": {"direction_intent": "long"},
        },
        {
            "ts_ms": 1710000000002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "execution_decider_request",
            "payload": {"direction_intent": "none"},
        },
        {
            "ts_ms": 1710000000003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "execution_decider_request",
            "payload": {"direction_intent": "neutral"},
        },
        {
            "ts_ms": 1710000000004,
            "record_type": "agent_output",
            "event_id": "evt-4",
            "agent_name": "execution_decider",
            "payload": {"execution_action": "hold"},
        },
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--output", str(out_path), "--limit", "10"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    report = json.loads(out_path.read_text(encoding="utf-8"))
    summary = dict(report.get("summary") or {})
    assert report.get("schema_version") == "agent-execution-direction-intent-report-v1"
    assert summary.get("execution_decider_request_count") == 3
    assert summary.get("direction_intent_total") == 3
    assert summary.get("long_count") == 1
    assert summary.get("neutral_count") == 1
    assert summary.get("none_count") == 1
    assert summary.get("invalid_count") == 0
    none_samples = list(report.get("none_samples") or [])
    assert len(none_samples) == 1
    assert none_samples[0]["event_id"] == "evt-2"
