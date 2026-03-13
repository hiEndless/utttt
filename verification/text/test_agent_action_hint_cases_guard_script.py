from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_agent_action_hint_cases_guard.sh"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_agent_action_hint_cases_guard_pass_when_within_limit(tmp_path: Path) -> None:
    report = tmp_path / "agent_action_hint_cases.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-action-hint-cases-v1",
            "count": 1,
            "rows": [{"event_id": "evt-1", "status": "mismatch", "expected_hint": "hold", "actual_hint": "add"}],
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "1"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] action_hint cases guard" in result.stdout


def test_agent_action_hint_cases_guard_fail_when_exceeds_limit(tmp_path: Path) -> None:
    report = tmp_path / "agent_action_hint_cases.latest.json"
    _write_json(
        report,
        {
            "schema_version": "agent-action-hint-cases-v1",
            "count": 2,
            "rows": [
                {"event_id": "evt-1", "status": "mismatch", "expected_hint": "hold", "actual_hint": "add"},
                {"event_id": "evt-2", "status": "mismatch", "expected_hint": "hold", "actual_hint": "add"},
            ],
        },
    )
    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(report), "1"],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "[failed] action_hint cases guard" in result.stdout
    assert "event_id=evt-1" in result.stdout
