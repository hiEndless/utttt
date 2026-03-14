from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "check_execution_direction_intent_residual_guard.sh"


def _write_report(path: Path, *, total: int, noncanonical_none_count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "execution-direction-intent-residual-report-v1",
                "summary": {
                    "direction_intent_total": total,
                    "noncanonical_none_count": noncanonical_none_count,
                },
                "noncanonical_none_examples": [
                    {"line_no": 2, "event_id": "dec-2", "path": "$.order_result.direction_intent", "value": "none"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_check_execution_direction_intent_residual_guard_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "max_none" in out
    assert "min_total" in out


def test_check_execution_direction_intent_residual_guard_pass(tmp_path: Path) -> None:
    report_path = tmp_path / "execution_direction_report.json"
    _write_report(report_path, total=10, noncanonical_none_count=0)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[passed] execution direction_intent residual guard" in str(proc.stdout or "")


def test_check_execution_direction_intent_residual_guard_fail(tmp_path: Path) -> None:
    report_path = tmp_path / "execution_direction_report.json"
    _write_report(report_path, total=10, noncanonical_none_count=2)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    out = str(proc.stdout or "")
    assert "[failed] execution direction_intent residual guard" in out
    assert "noncanonical_none_count=2" in out


def test_check_execution_direction_intent_residual_guard_skip_on_low_sample(tmp_path: Path) -> None:
    report_path = tmp_path / "execution_direction_report.json"
    _write_report(report_path, total=0, noncanonical_none_count=0)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "5"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[skip] execution direction_intent residual guard: insufficient samples" in str(proc.stdout or "")
