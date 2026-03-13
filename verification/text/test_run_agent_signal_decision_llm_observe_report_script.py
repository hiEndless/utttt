from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_signal_decision_llm_observe_report.sh"


def test_run_agent_signal_decision_llm_observe_report_help() -> None:
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
    assert "decision_mode" in out
    assert "llm_parse_status" in out


def test_run_agent_signal_decision_llm_observe_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "agent_events.jsonl"
    out_path = tmp_path / "llm_observe_report.json"
    rows = [
        {
            "ts_ms": 1710000000001,
            "record_type": "agent_output",
            "event_id": "evt-1",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "social_news", "decision_mode": "rule", "llm_parse_status": "rule_only"}},
        },
        {
            "ts_ms": 1710000000002,
            "record_type": "agent_output",
            "event_id": "evt-2",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "social_news", "decision_mode": "rule_fallback", "llm_parse_status": "llm_invalid_payload"}},
        },
        {
            "ts_ms": 1710000000003,
            "record_type": "agent_output",
            "event_id": "evt-3",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "onchain", "decision_mode": "llm", "llm_parse_status": "llm_ok"}},
        },
        {
            "ts_ms": 1710000000004,
            "record_type": "agent_output",
            "event_id": "evt-4",
            "agent_name": "decision_trace",
            "payload": {"routing": {"decision_agent_key": "technical"}},
        },
        {
            "ts_ms": 1710000000005,
            "record_type": "agent_output",
            "event_id": "evt-5",
            "agent_name": "other_agent",
            "payload": {"routing": {"decision_mode": "rule", "llm_parse_status": "rule_only"}},
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
    assert report["schema_version"] == "agent-signal-decision-llm-observe-report-v1"
    summary = dict(report["summary"])
    assert summary["decision_trace_record_count"] == 4
    assert summary["decision_trace_event_count"] == 4
    assert summary["missing_decision_mode_count"] == 1
    assert summary["missing_llm_parse_status_count"] == 1
    assert summary["decision_mode"]["rule"] == 1
    assert summary["decision_mode"]["rule_fallback"] == 1
    assert summary["decision_mode"]["llm"] == 1
    assert summary["decision_mode"]["missing"] == 1
    assert summary["llm_parse_status"]["rule_only"] == 1
    assert summary["llm_parse_status"]["llm_invalid_payload"] == 1
    assert summary["llm_parse_status"]["llm_ok"] == 1
    assert summary["llm_parse_status"]["missing"] == 1
    per_keys = {str(x["decision_agent_key"]): x for x in list(report["per_agent_key"] or [])}
    assert "social_news" in per_keys
    assert per_keys["social_news"]["record_count"] == 2
