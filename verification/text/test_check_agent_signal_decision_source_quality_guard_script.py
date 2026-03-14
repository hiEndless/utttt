from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_agent_signal_decision_source_quality_guard.sh"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _base_report() -> dict:
    return {
        "schema_version": "agent-signal-decision-replay-report-v1",
        "source_decision_mode_counts": [
            {"signal_source_type": "social_news", "decision_mode": "rule", "count": 6},
            {"signal_source_type": "social_news", "decision_mode": "llm", "count": 4},
        ],
        "source_llm_parse_status_counts": [
            {"signal_source_type": "social_news", "llm_parse_status": "llm_ok", "count": 4},
        ],
    }


def test_signal_decision_source_quality_guard_pass(tmp_path: Path) -> None:
    report = tmp_path / "agent_signal_decision_replay.latest.json"
    _write_json(report, _base_report())
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "10", "-1", "-1", "-1", "0.30"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] source=social_news llm_ok_ratio=0.400000" in result.stdout


def test_signal_decision_source_quality_guard_fail(tmp_path: Path) -> None:
    report = tmp_path / "agent_signal_decision_replay.latest.json"
    _write_json(report, _base_report())
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "10", "-1", "-1", "-1", "0.50"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "[failed] signal decision source quality guard" in result.stdout
    assert "source=social_news llm_ok_ratio=0.400000 < min_ratio=0.500000" in result.stdout


def test_signal_decision_source_quality_guard_skip_when_disabled(tmp_path: Path) -> None:
    report = tmp_path / "agent_signal_decision_replay.latest.json"
    _write_json(report, _base_report())
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "10", "-1", "-1", "-1", "-1"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[skip] signal decision source quality guard disabled" in result.stdout


def test_signal_decision_source_quality_guard_global_ratio_pass(tmp_path: Path) -> None:
    report = tmp_path / "agent_signal_decision_replay.latest.json"
    _write_json(report, _base_report())
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "10", "-1", "-1", "-1", "-1", "0.30", "0.30"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] global decision_mode_llm_ratio=0.400000" in result.stdout
    assert "[passed] global llm_ok_ratio=0.400000" in result.stdout


def test_signal_decision_source_quality_guard_global_ratio_fail(tmp_path: Path) -> None:
    report = tmp_path / "agent_signal_decision_replay.latest.json"
    _write_json(report, _base_report())
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "10", "-1", "-1", "-1", "-1", "0.50", "0.50"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "global decision_mode_llm_ratio=0.400000 < min_ratio=0.500000" in result.stdout
    assert "global llm_ok_ratio=0.400000 < min_ratio=0.500000" in result.stdout
