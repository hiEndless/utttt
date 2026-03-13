from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "inspect_agent_action_hint_cases.sh"


def test_inspect_agent_action_hint_cases_help() -> None:
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
    assert "--limit <n>" in out
    assert "--status <type>" in out


def test_inspect_agent_action_hint_cases_output_and_status_filter(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    rows = [
        {
            "ts_ms": 1710000002101,
            "record_type": "agent_output",
            "event_id": "evt-ok",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "accept", "direction": "long"}},
        },
        {
            "ts_ms": 1710000002102,
            "record_type": "agent_output",
            "event_id": "evt-mismatch",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "reject", "direction": "long"}},
        },
        {
            "ts_ms": 1710000002103,
            "record_type": "agent_output",
            "event_id": "evt-missing",
            "agent_name": "decision_trace",
            "payload": {"routing": {"pipeline_mode": "minimal"}, "signal_verdict": {"verdict": "accept", "direction": "none"}},
        },
        {
            "ts_ms": 1710000002201,
            "record_type": "agent_output",
            "event_id": "evt-ok",
            "agent_name": "execution_decider",
            "payload": {"risk_hints": {"agent_action_hint": "add"}},
        },
        {
            "ts_ms": 1710000002202,
            "record_type": "agent_output",
            "event_id": "evt-mismatch",
            "agent_name": "execution_decider",
            "payload": {"risk_hints": {"agent_action_hint": "add"}},
        },
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    all_proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--limit", "10", "--status", "all"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert all_proc.returncode == 0
    out_all = str(all_proc.stdout or "")
    assert "event_id\tverdict\tdirection\texpected_hint\tactual_hint\tstatus" in out_all
    assert "evt-ok\taccept\tlong\tadd\tadd\tok" in out_all
    assert "evt-mismatch\treject\tlong\thold\tadd\tmismatch" in out_all
    assert "evt-missing\taccept\tnone\thold\t\tmissing" in out_all

    mismatch_proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--status", "mismatch"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert mismatch_proc.returncode == 0
    out_mismatch = str(mismatch_proc.stdout or "")
    assert "evt-mismatch" in out_mismatch
    assert "evt-ok" not in out_mismatch
    assert "evt-missing" not in out_mismatch
