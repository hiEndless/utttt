from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_action_hint_semantics_summary.sh"


def test_print_action_hint_semantics_summary_help() -> None:
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
    assert "action_hint_semantics" in out


def test_print_action_hint_semantics_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    payload = {
        "action_hint_semantics_minimal_decision_count": 12,
        "action_hint_semantics_actual_hint_available_count": 10,
        "action_hint_semantics_match_count": 9,
        "action_hint_semantics_mismatch_count": 1,
        "action_hint_semantics_missing_actual_hint_count": 2,
        "action_hint_semantics_match_ratio_on_available": 0.9,
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
    assert "[nightly] action_hint_semantics_summary" in out
    assert "minimal_decision_count=12 actual_hint_available_count=10" in out
    assert "match_count=9 mismatch_count=1 missing_actual_hint_count=2" in out
    assert "match_ratio_on_available=0.900000" in out
