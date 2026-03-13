from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "check_agent_execution_closed_loop_smoke.sh"


def test_check_agent_execution_closed_loop_smoke_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "accept->0 / reject->0 / error->2" in out


def test_check_agent_execution_closed_loop_smoke_runs_three_modes() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[ok] mode=accept exit=0" in out
    assert "[ok] mode=reject exit=0" in out
    assert "[ok] mode=error exit=2" in out
    assert "[ok] closed loop smoke exits verified" in out

