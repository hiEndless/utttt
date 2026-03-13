from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_agent_signal_decision_replay_trend.sh"


def test_print_agent_signal_decision_replay_trend_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--glob <pattern>" in out
    assert "--source <type>" in out
    assert "--days <n>" in out
    assert "--output <path>" in out


def test_print_agent_signal_decision_replay_trend_output(tmp_path: Path) -> None:
    def _write(name: str, generated_at_ms: int, social_rule: int, social_fallback: int) -> None:
        payload = {
            "schema_version": "agent-signal-decision-replay-report-v1",
            "generated_at_ms": generated_at_ms,
            "source_decision_mode_counts": [
                {"signal_source_type": "social_news", "decision_mode": "rule", "count": social_rule},
                {"signal_source_type": "social_news", "decision_mode": "rule_fallback", "count": social_fallback},
            ],
        }
        (tmp_path / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    # 2026-03-14 / 2026-03-13 UTC
    _write("agent_signal_decision_replay.a.json", 1773446400000, 8, 2)
    _write("agent_signal_decision_replay.b.json", 1773360000000, 5, 5)
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--glob",
            str(tmp_path / "agent_signal_decision_replay*.json"),
            "--source",
            "social_news",
            "--days",
            "7",
            "--prefix",
            "nightly",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[nightly] signal_decision_replay_trend" in out
    assert "source=social_news" in out
    assert "reports=2" in out
    assert "fallback=7" in out


def test_print_agent_signal_decision_replay_trend_output_file(tmp_path: Path) -> None:
    payload = {
        "schema_version": "agent-signal-decision-replay-report-v1",
        "generated_at_ms": 1773446400000,
        "source_decision_mode_counts": [
            {"signal_source_type": "social_news", "decision_mode": "rule", "count": 9},
            {"signal_source_type": "social_news", "decision_mode": "rule_fallback", "count": 1},
        ],
    }
    replay_path = tmp_path / "agent_signal_decision_replay.single.json"
    replay_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    trend_path = tmp_path / "agent_signal_decision_replay_trend.latest.json"
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--glob",
            str(tmp_path / "agent_signal_decision_replay*.json"),
            "--output",
            str(trend_path),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "[ok] wrote " in out
    assert trend_path.exists()
    trend = json.loads(trend_path.read_text(encoding="utf-8"))
    assert trend["schema_version"] == "agent-signal-decision-replay-trend-v1"
    assert trend["source_type"] == "social_news"
