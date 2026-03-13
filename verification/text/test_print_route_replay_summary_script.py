from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_route_replay_summary.sh"


def test_print_route_replay_summary_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--summary <path>" in out
    assert "--prefix <name>" in out


def test_print_route_replay_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    payload = {
        "route_replay_ok": False,
        "route_replay_count": 4,
        "route_replay_mismatch_count": 1,
        "route_replay_match_ratio": 0.75,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--summary", str(summary_path), "--prefix", "quick"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[quick] route_replay_summary" in out
    assert "ok=false count=4 mismatch=1" in out
    assert "match_ratio=0.750000" in out
