from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_decision_agent_key_summary.sh"


def test_print_decision_agent_key_summary_help() -> None:
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
    assert "decision_agent_key" in out


def test_print_decision_agent_key_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    payload = {
        "decision_agent_key_technical_count": 3,
        "decision_agent_key_onchain_count": 2,
        "decision_agent_key_liquidation_count": 1,
        "decision_agent_key_social_news_count": 2,
        "decision_agent_key_generic_count": 1,
        "decision_agent_key_unknown_count": 1,
        "decision_agent_key_unknown_ratio": 0.1,
        "decision_agent_key_core_four_coverage_ratio": 0.8,
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
    assert "[nightly] decision_agent_key_summary" in out
    assert "technical=3 onchain=2 liquidation=1 social_news=2 generic=1 unknown=1" in out
    assert "unknown_ratio=0.100000 core_four_coverage_ratio=0.800000" in out
