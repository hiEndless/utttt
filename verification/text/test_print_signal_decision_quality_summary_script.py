from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_quality_summary.sh"


def test_print_signal_decision_quality_summary_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--report <path>" in out
    assert "--prefix <name>" in out
    assert "rule_fallback" in out


def test_print_signal_decision_quality_summary_output(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_signal_decision_replay.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-report-v1",
                "source_decision_mode_counts": [
                    {"signal_source_type": "social_news", "decision_mode": "rule", "count": 2},
                    {"signal_source_type": "social_news", "decision_mode": "rule_fallback", "count": 1},
                    {"signal_source_type": "social_news", "decision_mode": "llm", "count": 1},
                ],
                "source_llm_parse_status_counts": [
                    {"signal_source_type": "social_news", "llm_parse_status": "llm_ok", "count": 1},
                ],
                "source_verdict_counts": [
                    {"signal_source_type": "social_news", "signal_verdict": "accept", "count": 2},
                    {"signal_source_type": "social_news", "signal_verdict": "reject", "count": 1},
                    {"signal_source_type": "social_news", "signal_verdict": "uncertain", "count": 1},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--report", str(report_path), "--prefix", "nightly"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[nightly] signal_decision_quality_summary source=social_news" in out
    assert "llm=1" in out
    assert "rule_fallback=1" in out
    assert "rule=2" in out
    assert "accept=2" in out
    assert "reject=1" in out
    assert "uncertain=1" in out
