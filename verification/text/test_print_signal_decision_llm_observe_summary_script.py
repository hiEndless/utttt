from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_llm_observe_summary.sh"


def test_print_signal_decision_llm_observe_summary_help() -> None:
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


def test_print_signal_decision_llm_observe_summary_output(tmp_path: Path) -> None:
    report_path = tmp_path / "llm_observe_report.json"
    payload = {
        "summary": {
            "decision_trace_record_count": 9,
            "decision_trace_event_count": 7,
            "decision_mode": {"rule": 4, "rule_fallback": 3, "llm": 2},
            "llm_parse_status": {"rule_only": 4, "llm_invalid_payload": 3, "llm_ok": 2},
        }
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--report", str(report_path), "--prefix", "regression"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[regression] signal_decision_llm_observe_summary" in out
    assert "records=9 events=7" in out
    assert "decision_mode={\"llm\": 2, \"rule\": 4, \"rule_fallback\": 3}" in out
    assert "llm_parse_status={\"llm_invalid_payload\": 3, \"llm_ok\": 2, \"rule_only\": 4}" in out
