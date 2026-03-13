from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_llm_observe_trend_recommendation_hint.sh"


def test_print_signal_decision_llm_observe_trend_recommendation_hint_help() -> None:
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


def test_print_signal_decision_llm_observe_trend_recommendation_hint_recommend(tmp_path: Path) -> None:
    report_path = tmp_path / "recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1",
                "status": "recommend",
                "reason": "low_llm_ok_ratio_consecutive_days",
                "recommend_action": "review_llm_prompt_or_model_routing",
                "warn_agent_keys": ["social_news", "technical"],
                "reports": 7,
                "window_days": 7,
                "min_ratio": 0.15,
                "min_consecutive_days": 3,
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
    assert "[release-candidate] llm_observe status=recommend" in out
    assert "warn_agent_keys=social_news,technical" in out


def test_print_signal_decision_llm_observe_trend_recommendation_hint_hold(tmp_path: Path) -> None:
    report_path = tmp_path / "recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1",
                "status": "hold",
                "reason": "all_agent_keys_stable",
                "recommend_action": "none",
                "warn_agent_keys": [],
                "reports": 7,
                "window_days": 7,
                "min_ratio": 0.15,
                "min_consecutive_days": 3,
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
    assert "[release-hold] llm_observe status=hold" in out
    assert "warn_agent_keys=none" in out
