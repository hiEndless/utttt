from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_semantic_critical_warning_guard.sh"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_semantic_critical_warning_guard_pass_when_no_critical_hit(tmp_path: Path) -> None:
    audit = tmp_path / "semantic_audit.latest.json"
    budget = tmp_path / "semantic_critical_fields.yaml"
    _write_json(
        audit,
        {
            "schema_version": "semantic-audit-v1",
            "warnings": [
                "field random_field: weak semantics",
            ],
        },
    )
    _write_yaml(
        budget,
        "version: 2\nupdated_at: '2026-03-13'\ncritical_fields:\n  - provider_state\n  - decision_confidence\n",
    )

    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(audit), str(budget)],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[passed] semantic critical warning guard" in result.stdout


def test_semantic_critical_warning_guard_fail_when_provider_state_hit(tmp_path: Path) -> None:
    audit = tmp_path / "semantic_audit.latest.json"
    budget = tmp_path / "semantic_critical_fields.yaml"
    _write_json(
        audit,
        {
            "schema_version": "semantic-audit-v1",
            "warnings": [
                "field provider_state: enum drift detected",
            ],
        },
    )
    _write_yaml(
        budget,
        "version: 2\nupdated_at: '2026-03-13'\ncritical_fields:\n  - provider_state\n",
    )

    result = subprocess.run(
        ["bash", str(GUARD_SCRIPT), str(audit), str(budget)],
        cwd=str(PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "[failed] semantic critical warning guard" in result.stdout
    assert "field provider_state: enum drift detected" in result.stdout
