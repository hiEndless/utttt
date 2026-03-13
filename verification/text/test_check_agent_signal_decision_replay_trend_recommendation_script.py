from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "check_agent_signal_decision_replay_trend_recommendation.sh"


def _write_trend(path: Path, ratio: float, latest_ratio: float, total: int, days: int, daily_rows: list[dict]) -> None:
    payload = {
        "schema_version": "agent-signal-decision-replay-trend-v1",
        "source_type": "social_news",
        "window_days": 7,
        "reports": 7,
        "days": days,
        "total": total,
        "fallback": int(round(total * ratio)),
        "ratio": ratio,
        "latest_day": "2026-03-14",
        "latest_ratio": latest_ratio,
        "daily_rows": daily_rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_check_agent_signal_decision_replay_trend_recommendation_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "recommend_ratio" in out
    assert "min_consecutive_days" in out


def test_check_agent_signal_decision_replay_trend_recommendation_recommend(tmp_path: Path) -> None:
    trend_path = tmp_path / "trend.json"
    _write_trend(
        trend_path,
        ratio=0.65,
        latest_ratio=0.60,
        total=40,
        days=7,
        daily_rows=[
            {"day": "2026-03-12", "total": 10, "fallback": 6, "ratio": 0.60},
            {"day": "2026-03-13", "total": 10, "fallback": 6, "ratio": 0.60},
            {"day": "2026-03-14", "total": 20, "fallback": 12, "ratio": 0.60},
        ],
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(trend_path), "0.70", "3", "20"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[recommend] tighten_social_news_fallback_ratio_to_0_80" in str(proc.stdout or "")


def test_check_agent_signal_decision_replay_trend_recommendation_hold(tmp_path: Path) -> None:
    trend_path = tmp_path / "trend.json"
    _write_trend(
        trend_path,
        ratio=0.75,
        latest_ratio=0.80,
        total=40,
        days=7,
        daily_rows=[
            {"day": "2026-03-12", "total": 10, "fallback": 8, "ratio": 0.80},
            {"day": "2026-03-13", "total": 10, "fallback": 8, "ratio": 0.80},
            {"day": "2026-03-14", "total": 20, "fallback": 16, "ratio": 0.80},
        ],
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(trend_path), "0.70", "3", "20"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[hold] trend_recommendation" in str(proc.stdout or "")


def test_check_agent_signal_decision_replay_trend_recommendation_output_file(tmp_path: Path) -> None:
    trend_path = tmp_path / "trend.json"
    out_path = tmp_path / "recommendation.latest.json"
    _write_trend(
        trend_path,
        ratio=0.65,
        latest_ratio=0.60,
        total=40,
        days=7,
        daily_rows=[
            {"day": "2026-03-12", "total": 10, "fallback": 6, "ratio": 0.60},
            {"day": "2026-03-13", "total": 10, "fallback": 6, "ratio": 0.60},
            {"day": "2026-03-14", "total": 20, "fallback": 12, "ratio": 0.60},
        ],
    )
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), str(trend_path), "0.70", "3", "20", str(out_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "[ok] wrote " in str(proc.stdout or "")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "agent-signal-decision-replay-trend-recommendation-v1"
    assert payload["status"] == "recommend"
    assert payload["recommend_action"] == "tighten_social_news_fallback_ratio_to_0_80"
