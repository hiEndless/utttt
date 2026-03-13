from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_llm_observe_agent_key_coverage.sh"


def test_print_signal_decision_llm_observe_agent_key_coverage_help() -> None:
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


def test_print_signal_decision_llm_observe_agent_key_coverage_output(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_signal_decision_llm_observe.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "per_agent_key": [
                    {
                        "decision_agent_key": "social_news",
                        "record_count": 10,
                        "llm_parse_status": {"llm_ok": 4, "rule_only": 6},
                    },
                    {
                        "decision_agent_key": "onchain",
                        "record_count": 5,
                        "llm_parse_status": {"llm_ok": 1, "llm_invalid_payload": 4},
                    },
                ]
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
    assert "agent_key=social_news records=10 llm_ok=4 llm_ok_ratio=0.400000" in out
    assert "agent_key=onchain records=5 llm_ok=1 llm_ok_ratio=0.200000" in out
