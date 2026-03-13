from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_llm_observe_aggregate_summary.sh"


def test_print_signal_decision_llm_observe_aggregate_summary_help() -> None:
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


def test_print_signal_decision_llm_observe_aggregate_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.latest.json"
    payload = {
        "signal_decision_llm_observe_record_count": 15,
        "signal_decision_llm_observe_event_count": 13,
        "signal_decision_llm_observe_decision_mode_rule_count": 8,
        "signal_decision_llm_observe_decision_mode_rule_fallback_count": 4,
        "signal_decision_llm_observe_decision_mode_llm_count": 2,
        "signal_decision_llm_observe_decision_mode_missing_count": 1,
        "signal_decision_llm_observe_llm_parse_status_llm_ok_count": 2,
        "signal_decision_llm_observe_llm_parse_status_llm_invalid_payload_count": 4,
        "signal_decision_llm_observe_llm_parse_status_rule_only_count": 8,
        "signal_decision_llm_observe_llm_parse_status_llm_status_not_ok_count": 0,
        "signal_decision_llm_observe_llm_parse_status_llm_not_provided_count": 0,
        "signal_decision_llm_observe_llm_parse_status_missing_count": 1,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--summary", str(summary_path), "--prefix", "nightly"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[nightly] signal_decision_llm_observe_aggregate_summary" in out
    assert "records=15 events=13" in out
    assert "mode_rule=8 mode_rule_fallback=4 mode_llm=2 mode_missing=1" in out
    assert "status_llm_ok=2 status_llm_invalid_payload=4 status_rule_only=8" in out
