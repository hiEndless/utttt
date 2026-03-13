from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "verify_quick_report.sh"


def test_verify_quick_report_help_contains_pipeline_mode_flag() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--with-pipeline-mode-report" in out
    assert "--pipeline-mode-report-path <path>" in out


def test_verify_quick_report_calls_print_pipeline_mode_summary_script() -> None:
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "tools/local/print_pipeline_mode_summary.sh" in text
