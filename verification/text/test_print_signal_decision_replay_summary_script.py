from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_replay_summary.sh"


def test_print_signal_decision_replay_summary_help() -> None:
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


def test_print_signal_decision_replay_summary_output(tmp_path: Path) -> None:
    report_path = tmp_path / "signal_decision_replay.json"
    payload = {
        "summary": {
            "decision_trace_record_count": 8,
            "route_match_count": 7,
            "route_mismatch_count": 1,
            "route_match_ratio": 0.875,
            "accept_count": 3,
            "reject_count": 2,
            "uncertain_count": 3,
            "decision_mode_rule_count": 5,
            "decision_mode_rule_fallback_count": 2,
            "decision_mode_llm_count": 1,
        }
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--report", str(report_path), "--prefix", "quick"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[quick] signal_decision_replay_summary" in out
    assert "records=8 route_match=7 route_mismatch=1 route_match_ratio=0.875000" in out
    assert "accept=3 reject=2 uncertain=3 rule=5 rule_fallback=2 llm=1" in out
