from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_pipeline_mode_report.sh"


def test_run_agent_pipeline_mode_report_help() -> None:
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
    assert "pipeline_mode" in out


def test_run_agent_pipeline_mode_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "pipeline_mode_report.json"
    rows = [
        {
            "ts_ms": 1710000000001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "legacy"}},
        },
        {
            "ts_ms": 1710000000002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}},
        },
        {
            "ts_ms": 1710000000003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "future_mode"}},
        },
        {
            "ts_ms": 1710000000004,
            "record_type": "agent_output",
            "event_id": "evt-4",
            "agent_name": "decision_trace",
            "payload": {"routing": {}},
        },
        {
            "ts_ms": 1710000000005,
            "record_type": "agent_output",
            "event_id": "evt-5",
            "agent_name": "other_agent",
            "payload": {"routing": {"pipeline_mode": "legacy"}},
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
    assert summary["decision_trace_record_count"] == 4
    assert summary["decision_trace_event_count"] == 4
    assert summary["minimal_count"] == 1
    assert summary["unknown_count"] == 2
    assert summary["missing_pipeline_mode_count"] == 1
    assert summary["minimal_ratio"] == 0.333333
    assert len(report["unknown_samples"]) == 2
    assert report["unknown_samples"][0]["pipeline_mode"] == "legacy"
    assert report["unknown_samples"][1]["pipeline_mode"] == "future_mode"
