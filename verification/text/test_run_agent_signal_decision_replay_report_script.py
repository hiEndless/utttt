from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_signal_decision_replay_report.sh"


def test_run_agent_signal_decision_replay_report_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--input <path>" in out
    assert "--output <path>" in out
    assert "--limit <n>" in out
    assert "signal_verdict" in out


def test_run_agent_signal_decision_replay_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "signal_decision_replay_report.json"
    rows = [
        {
            "ts_ms": 1710000001001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {
                "event": {"signal_source_type": "market_indicator"},
                "signal_verdict": {"verdict": "accept", "direction": "long"},
                "routing": {
                    "decision_agent_key": "technical",
                    "decision_mode": "rule",
                    "llm_parse_status": "rule_only",
                    "pipeline_mode": "minimal",
                },
            },
        },
        {
            "ts_ms": 1710000001002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {
                "event": {"signal_source_type": "social_news"},
                "signal_verdict": {"verdict": "reject", "direction": "none"},
                "routing": {
                    "decision_agent_key": "social_news",
                    "decision_mode": "llm",
                    "llm_parse_status": "llm_ok",
                    "pipeline_mode": "minimal",
                },
            },
        },
        {
            "ts_ms": 1710000001003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {
                "event": {"signal_source_type": "onchain_wallet"},
                "signal_verdict": {"verdict": "uncertain", "direction": "none"},
                "routing": {
                    "decision_agent_key": "generic",
                    "decision_mode": "rule_fallback",
                    "llm_parse_status": "llm_invalid_payload",
                    "pipeline_mode": "minimal",
                },
            },
        },
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--output", str(out_path), "--limit", "2"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_path.exists()

    report = json.loads(out_path.read_text(encoding="utf-8"))
    summary = dict(report["summary"])
    assert report["schema_version"] == "agent-signal-decision-replay-report-v1"
    assert summary["decision_trace_record_count"] == 3
    assert summary["decision_trace_event_count"] == 3
    assert summary["route_match_count"] == 2
    assert summary["route_mismatch_count"] == 1
    assert summary["route_match_ratio"] == 0.666667
    assert summary["accept_count"] == 1
    assert summary["reject_count"] == 1
    assert summary["uncertain_count"] == 1
    assert summary["decision_mode_rule_count"] == 1
    assert summary["decision_mode_llm_count"] == 1
    assert summary["decision_mode_rule_fallback_count"] == 1
    latest_rows = list(report["latest_rows"])
    assert len(latest_rows) == 2
    assert latest_rows[0]["event_id"] == "evt-3"
    assert latest_rows[1]["event_id"] == "evt-2"
