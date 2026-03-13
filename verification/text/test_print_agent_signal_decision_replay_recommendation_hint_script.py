from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_agent_signal_decision_replay_recommendation_hint.sh"


def test_print_agent_signal_decision_replay_recommendation_hint_help() -> None:
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
    assert "[release-candidate]" in out


def test_print_agent_signal_decision_replay_recommendation_hint_recommend(tmp_path: Path) -> None:
    report_path = tmp_path / "recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-trend-recommendation-v1",
                "status": "recommend",
                "recommend_action": "tighten_social_news_fallback_ratio_to_0_80",
                "source_type": "social_news",
                "ratio": 0.61,
                "latest_ratio": 0.58,
                "consecutive_days": 4,
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
    out = str(proc.stdout or "")
    assert "[release-candidate] source=social_news" in out


def test_print_agent_signal_decision_replay_recommendation_hint_hold(tmp_path: Path) -> None:
    report_path = tmp_path / "recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-trend-recommendation-v1",
                "status": "hold",
                "reason": "ratio_not_stable_below_threshold",
                "source_type": "social_news",
                "ratio": 0.72,
                "latest_ratio": 0.75,
                "consecutive_days": 1,
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
    out = str(proc.stdout or "")
    assert "[release-hold] source=social_news status=hold" in out
