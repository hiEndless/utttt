from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_event_type_match_summary.sh"


def test_print_event_type_match_summary_help() -> None:
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
    assert "event_type_match" in out


def test_print_event_type_match_summary_output(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    payload = {
        "event_type_match_alias_count": 4,
        "event_type_match_canonical_or_raw_count": 6,
        "event_type_match_unknown_count": 1,
        "event_type_match_missing_count": 2,
        "event_type_match_alias_ratio": 0.4,
        "event_type_match_canonical_or_raw_ratio": 0.6,
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--summary", str(summary_path), "--prefix", "regression"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[regression] event_type_match_summary" in out
    assert "alias=4 canonical_or_raw=6 unknown=1 missing=2" in out
    assert "alias_ratio=0.400000 canonical_or_raw_ratio=0.600000" in out

