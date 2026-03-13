from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "print_signal_decision_llm_observe_agent_key_trend.sh"


def test_print_signal_decision_llm_observe_agent_key_trend_help() -> None:
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
    assert "--days <n>" in out
    assert "--min-ratio <float>" in out
    assert "--agent-keys <csv>" in out


def test_print_signal_decision_llm_observe_agent_key_trend_output(tmp_path: Path) -> None:
    def _write(name: str, ts_ms: int, social_records: int, social_llm_ok: int) -> None:
        payload = {
            "schema_version": "agent-signal-decision-llm-observe-report-v1",
            "generated_at_ms": ts_ms,
            "per_agent_key": [
                {
                    "decision_agent_key": "social_news",
                    "record_count": social_records,
                    "llm_parse_status": {"llm_ok": social_llm_ok, "rule_only": max(0, social_records - social_llm_ok)},
                }
            ],
        }
        (tmp_path / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    _write("llm_observe.a.json", 1773446400000, 10, 1)  # 0.10
    _write("llm_observe.b.json", 1773360000000, 10, 1)  # 0.10
    out_path = tmp_path / "trend.latest.json"
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--glob",
            str(tmp_path / "llm_observe*.json"),
            "--days",
            "7",
            "--min-ratio",
            "0.15",
            "--min-consecutive-days",
            "2",
            "--agent-keys",
            "social_news",
            "--output",
            str(out_path),
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
    assert "[warn] nightly signal_decision_llm_observe_agent_key_trend agent_key=social_news" in out
    assert out_path.exists()
    trend = json.loads(out_path.read_text(encoding="utf-8"))
    assert trend["schema_version"] == "agent-signal-decision-llm-observe-agent-key-trend-v1"
    assert trend["rows"][0]["agent_key"] == "social_news"
