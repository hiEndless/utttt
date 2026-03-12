from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_tail_agent_events_help_contains_filter_options() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/tail_agent_events.sh", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--event-id <id>" in out
    assert "--agent-name <name>" in out
    assert "--record-type <type>" in out
    assert "--contains <keyword>" in out
    assert "--jq <expr>" in out
    assert "--pretty" in out


def test_tail_agent_events_filter_by_event_and_record_type(tmp_path) -> None:
    file_path = tmp_path / "agent_events.jsonl"
    rows = [
        {"record_type": "agent_output", "event_id": "evt-1", "agent_name": "decision_trace", "payload": {}},
        {"record_type": "market_context", "event_id": "evt-1", "payload": {}},
        {"record_type": "agent_output", "event_id": "evt-2", "agent_name": "decision_trace", "payload": {}},
    ]
    file_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            "bash",
            "tools/local/tail_agent_events.sh",
            str(file_path),
            "--no-follow",
            "--lines",
            "20",
            "--event-id",
            "evt-1",
            "--record-type",
            "agent_output",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out_lines = [x for x in str(proc.stdout or "").splitlines() if x.strip()]
    assert len(out_lines) == 1
    item = json.loads(out_lines[0])
    assert item["event_id"] == "evt-1"
    assert item["record_type"] == "agent_output"


def test_tail_agent_events_filter_by_contains_keyword(tmp_path) -> None:
    file_path = tmp_path / "agent_events.jsonl"
    rows = [
        {"record_type": "agent_output", "event_id": "evt-1", "agent_name": "decision_trace", "payload": {"note": "alpha"}},
        {"record_type": "agent_output", "event_id": "evt-2", "agent_name": "decision_trace", "payload": {"note": "beta"}},
    ]
    file_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            "bash",
            "tools/local/tail_agent_events.sh",
            str(file_path),
            "--no-follow",
            "--lines",
            "20",
            "--contains",
            "alpha",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out_lines = [x for x in str(proc.stdout or "").splitlines() if x.strip()]
    assert len(out_lines) == 1
    item = json.loads(out_lines[0])
    assert item["event_id"] == "evt-1"


def test_tail_agent_events_pretty_output(tmp_path) -> None:
    file_path = tmp_path / "agent_events.jsonl"
    rows = [
        {"record_type": "agent_output", "event_id": "evt-1", "agent_name": "decision_trace", "payload": {"note": "alpha"}},
    ]
    file_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            "bash",
            "tools/local/tail_agent_events.sh",
            str(file_path),
            "--no-follow",
            "--lines",
            "10",
            "--pretty",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "{\n" in out
    assert '"event_id": "evt-1"' in out
