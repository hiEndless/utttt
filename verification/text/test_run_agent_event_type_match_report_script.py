from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_event_type_match_report.sh"


def test_run_agent_event_type_match_report_help() -> None:
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
    assert "routing.event_type_*" in out


def test_run_agent_event_type_match_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "event_type_match_report.json"
    rows = [
        {
            "ts_ms": 1710000001001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {
                "routing": {
                    "decision_agent_key": "technical",
                    "event_type_raw": "market_indicator_signal",
                    "event_type_normalized": "market_indicator_signal",
                    "event_type_match_mode": "canonical_or_raw",
                }
            },
        },
        {
            "ts_ms": 1710000001002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {
                "routing": {
                    "decision_agent_key": "onchain",
                    "event_type_raw": "wallet_alert",
                    "event_type_normalized": "onchain_wallet_anomaly",
                    "event_type_match_mode": "alias",
                }
            },
        },
        {
            "ts_ms": 1710000001003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {
                "routing": {
                    "decision_agent_key": "generic",
                    "event_type_raw": "my_custom_event",
                    "event_type_normalized": "my_custom_event",
                    "event_type_match_mode": "canonical_or_raw",
                }
            },
        },
        {
            "ts_ms": 1710000001004,
            "record_type": "agent_output",
            "event_id": "evt-4",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "generic", "event_type_raw": "my_custom_event"}},
        },
        {
            "ts_ms": 1710000001005,
            "record_type": "agent_output",
            "event_id": "evt-5",
            "agent_name": "other_agent",
            "payload": {"routing": {"event_type_match_mode": "alias"}},
        },
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--output", str(out_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_path.exists()

    report = json.loads(out_path.read_text(encoding="utf-8"))
    summary = dict(report["summary"])
    assert report["schema_version"] == "agent-event-type-match-report-v1"
    assert summary["decision_trace_record_count"] == 4
    assert summary["decision_trace_event_count"] == 4
    assert summary["match_mode_canonical_or_raw_count"] == 2
    assert summary["match_mode_alias_count"] == 1
    assert summary["match_mode_empty_count"] == 0
    assert summary["missing_match_mode_count"] == 1
    assert summary["match_mode_alias_ratio"] == 0.333333
    assert summary["match_mode_canonical_or_raw_ratio"] == 0.666667
    top = list(report["top_unknown_event_types"])
    assert top
    assert top[0]["event_type_raw"] == "my_custom_event"
    assert top[0]["count"] == 2
