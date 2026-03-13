from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "read_agent_signal_decision_recommendation_status.sh"


def test_read_agent_signal_decision_recommendation_status_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "recommendation_json" in out
    assert "recommend | hold | skip" in out


def test_read_agent_signal_decision_recommendation_status_recommend(tmp_path: Path) -> None:
    report_path = tmp_path / "recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-trend-recommendation-v1",
                "status": "recommend",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(report_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert str(proc.stdout or "").strip() == "recommend"


def test_read_agent_signal_decision_recommendation_status_missing() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "verification/reports/not_found_recommendation.json"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert str(proc.stdout or "").strip() == "missing"
