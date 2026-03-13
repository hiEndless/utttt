from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "check_agent_signal_decision_replay_guard.sh"


def _write_report(path: Path, social_fallback: int, social_total: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-report-v1",
                "source_decision_mode_counts": [
                    {
                        "signal_source_type": "social_news",
                        "decision_mode": "rule_fallback",
                        "count": social_fallback,
                    },
                    {
                        "signal_source_type": "social_news",
                        "decision_mode": "rule",
                        "count": max(0, social_total - social_fallback),
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_check_agent_signal_decision_replay_guard_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "max_social_news_ratio" in out
    assert "min_source_count" in out


def test_check_agent_signal_decision_replay_guard_passes_within_threshold(tmp_path: Path) -> None:
    report_path = tmp_path / "signal_decision_replay.json"
    _write_report(report_path, social_fallback=2, social_total=10)
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            str(report_path),
            "5",
            "-1",
            "-1",
            "-1",
            "0.3",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[passed] source=social_news" in out


def test_check_agent_signal_decision_replay_guard_fails_when_threshold_exceeded(tmp_path: Path) -> None:
    report_path = tmp_path / "signal_decision_replay.json"
    _write_report(report_path, social_fallback=8, social_total=10)
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            str(report_path),
            "5",
            "-1",
            "-1",
            "-1",
            "0.3",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    out = str(proc.stdout or "")
    assert "[failed] signal decision replay guard" in out
    assert "source=social_news" in out


def test_check_agent_signal_decision_replay_guard_skips_when_all_thresholds_disabled(tmp_path: Path) -> None:
    report_path = tmp_path / "signal_decision_replay.json"
    _write_report(report_path, social_fallback=8, social_total=10)
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path), "5", "-1", "-1", "-1", "-1"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[skip] signal decision replay guard disabled" in out
