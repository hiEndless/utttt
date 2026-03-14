from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.validators.local_refs_schema import validate_payload_with_local_refs


def _schema() -> tuple[dict, Path]:
    schema_path = PROJECT_ROOT / "verification" / "reports" / "release_ready_report_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return schema, schema_path.parent


def test_release_ready_report_schema_accepts_passed_payload() -> None:
    schema, base = _schema()
    payload = {
        "schema_version": "release-ready-report-v1",
        "status": "passed",
        "failed_step": "",
        "message": "release ready checks passed",
        "steps": {
            "verify_quick": "passed",
            "single_path_release_gate": "passed",
            "new_arch_guards_quick": "passed",
            "release_triage_block_guard": "passed",
            "release_baseline_alignment": "passed",
        },
        "start_ts_ms": 1,
        "end_ts_ms": 2,
    }
    assert validate_payload_with_local_refs(schema, payload, base)


def test_release_ready_report_schema_accepts_failed_payload() -> None:
    schema, base = _schema()
    payload = {
        "schema_version": "release-ready-report-v1",
        "status": "failed",
        "failed_step": "single_path_release_gate",
        "message": "release ready checks failed",
        "steps": {
            "verify_quick": "passed",
            "single_path_release_gate": "failed",
            "new_arch_guards_quick": "pending",
            "release_triage_block_guard": "pending",
            "release_baseline_alignment": "pending",
        },
        "start_ts_ms": 1000,
        "end_ts_ms": 2000,
    }
    assert validate_payload_with_local_refs(schema, payload, base)
