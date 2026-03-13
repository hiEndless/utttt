from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.validators.local_refs_schema import validate_payload_with_local_refs


def test_release_gate_summary_json_matches_schema() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/check_release_ready.sh", "--print-summary-only", "--summary-format", "json"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "{}"))
    assert payload.get("source") == "tools/local/check_release_ready.sh"
    assert isinstance(payload.get("env_overrides"), list)
    assert isinstance(payload.get("ts_ms"), int)
    assert int(payload.get("ts_ms") or 0) > 0
    schema_path = PROJECT_ROOT / "verification" / "reports" / "release_gate_summary_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert validate_payload_with_local_refs(schema, payload, schema_path.parent)


def test_release_gate_summary_json_contains_env_overrides_when_set() -> None:
    env = dict(os.environ)
    env["MAX_AGENT_READYZ_LEVEL"] = "yellow"
    env["MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"] = "1"
    proc = subprocess.run(
        [
            "bash",
            "tools/local/check_release_ready.sh",
            "--print-summary-only",
            "--summary-format",
            "json",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "{}"))
    overrides = list(payload.get("env_overrides") or [])
    assert "MAX_AGENT_READYZ_LEVEL" in overrides
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in overrides


def test_release_gate_summary_json_contains_recommendation_artifact_block(tmp_path: Path) -> None:
    report_path = tmp_path / "agent_signal_decision_replay_recommendation.latest.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "agent-signal-decision-replay-trend-recommendation-v1",
                "status": "recommend",
                "recommend_action": "tighten_social_news_fallback_ratio_to_0_80",
            }
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH"] = str(report_path)
    proc = subprocess.run(
        [
            "bash",
            "tools/local/check_release_ready.sh",
            "--print-summary-only",
            "--summary-format",
            "json",
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(str(proc.stdout or "{}"))
    artifact = dict(payload.get("recommendation_artifact") or {})
    assert artifact.get("path") == str(report_path)
    assert artifact.get("status") == "recommend"
    assert artifact.get("recommend_action") == "tighten_social_news_fallback_ratio_to_0_80"
    assert "AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH" in list(payload.get("env_overrides") or [])
