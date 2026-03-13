from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_execution_closed_loop_smoke.sh"


def test_run_agent_execution_closed_loop_smoke_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--event-type <type>" in out
    assert "--signal-direction <dir>" in out
    assert "--result-mode <mode>" in out
    assert "execution_action/reject_reason" in out


def test_run_agent_execution_closed_loop_smoke_output() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "").strip())
    assert payload["signal_verdict"] == "accept"
    assert payload["signal_direction"] == "long"
    assert payload["execution_action"] == "hold"
    assert payload["reject_reason"] == "risk_limit_blocked"
    assert payload["decision_agent_key"] == "technical"


def test_run_agent_execution_closed_loop_smoke_output_error_mode() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--result-mode", "error"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "").strip())
    assert payload["execution_status"] == "error"
    assert payload["execution_action"] == ""
    assert payload["reject_reason"] == ""
