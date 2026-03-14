from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_pipeline_mode_summary.sh"


def test_print_pipeline_mode_summary_help() -> None:
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


def test_print_pipeline_mode_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    payload = {
        "pipeline_mode_minimal_count": 7,
        "pipeline_mode_unknown_count": 1,
        "pipeline_mode_missing_count": 2,
        "pipeline_mode_minimal_ratio": 0.875,
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
    assert "[quick] pipeline_mode_summary" in out
    assert "minimal=7 unknown=1 missing=2" in out
    assert "minimal_ratio=0.875000" in out
