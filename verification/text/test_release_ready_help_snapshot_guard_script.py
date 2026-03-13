from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_release_ready_help_snapshot_guard_script_passes() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/check_release_ready_help_snapshot_guard.sh"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = str(proc.stdout or "")
    assert "release ready help 快照守卫检查完成" in out
