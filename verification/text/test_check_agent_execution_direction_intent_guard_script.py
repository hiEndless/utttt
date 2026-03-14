from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "check_agent_execution_direction_intent_guard.sh"


def _write_report(path: Path, *, total: int, none_count: int, invalid_count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "agent-execution-direction-intent-report-v1",
                "summary": {
                    "direction_intent_total": total,
                    "none_count": none_count,
                    "invalid_count": invalid_count,
                },
                "none_samples": [{"line_no": 2, "event_id": "evt-none", "direction_intent": "none"}],
                "invalid_samples": [{"line_no": 3, "event_id": "evt-invalid", "direction_intent": "sideways"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_check_agent_execution_direction_intent_guard_help() -> None:
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
    assert "max_invalid" in out
    assert "min_total" in out


def test_check_agent_execution_direction_intent_guard_pass(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_execution_direction_intent_report.json"
    _write_report(report_path, total=10, none_count=0, invalid_count=0)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "0", "1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[passed] agent execution direction_intent guard" in str(proc.stdout or "")


def test_check_agent_execution_direction_intent_guard_fail_by_none(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_execution_direction_intent_report.json"
    _write_report(report_path, total=10, none_count=1, invalid_count=0)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "0", "1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    out = str(proc.stdout or "")
    assert "[failed] agent execution direction_intent guard" in out
    assert "none=1" in out


def test_check_agent_execution_direction_intent_guard_fail_by_invalid(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_execution_direction_intent_report.json"
    _write_report(report_path, total=10, none_count=0, invalid_count=2)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "0", "1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    out = str(proc.stdout or "")
    assert "[failed] agent execution direction_intent guard" in out
    assert "invalid=2" in out


def test_check_agent_execution_direction_intent_guard_skip_when_insufficient_samples(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_execution_direction_intent_report.json"
    _write_report(report_path, total=0, none_count=0, invalid_count=0)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "0", "0", "5"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[skip] agent execution direction_intent guard: insufficient samples" in str(proc.stdout or "")
