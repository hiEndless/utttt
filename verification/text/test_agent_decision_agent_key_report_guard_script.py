from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_agent_decision_agent_key_report_guard.sh"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_agent_decision_agent_key_report_guard_pass_when_within_limit(tmp_path: Path) -> None:
    report = tmp_path / "agent_decision_agent_key.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-decision-agent-key-report-v1",
            "summary": {"unknown_count": 1, "generic_count": 1, "decision_trace_record_count": 10, "generic_ratio": 0.1},
            "top_unknown_agent_keys": [{"decision_agent_key": "missing", "count": 1}],
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "1", "0.2"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] decision_agent_key guard" in result.stdout


def test_agent_decision_agent_key_report_guard_fail_when_exceeds_limit(tmp_path: Path) -> None:
    report = tmp_path / "agent_decision_agent_key.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-decision-agent-key-report-v1",
            "summary": {"unknown_count": 2, "generic_count": 1, "decision_trace_record_count": 10, "generic_ratio": 0.1},
            "top_unknown_agent_keys": [{"decision_agent_key": "custom_agent", "count": 2}],
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "1", "-1"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "[failed] decision_agent_key guard" in result.stdout
    assert "decision_agent_key=custom_agent" in result.stdout


def test_agent_decision_agent_key_report_guard_skip_when_limit_disabled(tmp_path: Path) -> None:
    report = tmp_path / "agent_decision_agent_key.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-decision-agent-key-report-v1",
            "summary": {"unknown_count": 999, "generic_count": 999, "decision_trace_record_count": 1000},
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "-1", "-1"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[skip] decision_agent_key guard disabled" in result.stdout


def test_agent_decision_agent_key_report_guard_fail_when_generic_ratio_exceeds_limit(tmp_path: Path) -> None:
    report = tmp_path / "agent_decision_agent_key.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-decision-agent-key-report-v1",
            "summary": {"unknown_count": 0, "generic_count": 5, "decision_trace_record_count": 10, "generic_ratio": 0.5},
            "top_unknown_agent_keys": [],
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "-1", "0.4"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "generic_ratio=0.500000" in result.stdout
