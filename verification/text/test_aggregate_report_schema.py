from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from verification.reports.aggregate_reports import build_summary
from verification.validators.local_refs_schema import validate_payload_with_local_refs


def test_aggregate_report_schema_validates_build_summary_output() -> None:
    schema_path = Path(PROJECT_ROOT) / "verification" / "reports" / "verification_report_aggregate_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    out = build_summary(
        [
            {
                "schema_version": "verification-report-v2",
                "suite": "quick",
                "status": "passed",
                "duration_ms": 100,
                "finished_at_ms": 1000,
            },
            {
                "schema_version": "symbol-memory-summary-run-v1",
                "ended_ms": 2000,
                "high_risk_symbols": [
                    {
                        "exchange": "binance",
                        "symbol": "ETHUSDT",
                        "contract_warning_count": 1,
                        "risk_score": 50.0,
                        "recent_contract_warning_types": ["alternative_sources_conflict_detected"],
                    }
                ],
            },
        ]
    )
    assert validate_payload_with_local_refs(schema, out, schema_path.parent)
