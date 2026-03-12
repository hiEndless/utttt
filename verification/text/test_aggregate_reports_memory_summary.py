from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from verification.reports.aggregate_reports import build_summary


def test_build_summary_includes_memory_high_risk_symbols() -> None:
    reports = [
        {
            "schema_version": "verification-report-v2",
            "suite": "quick",
            "status": "passed",
            "duration_ms": 100,
            "finished_at_ms": 1000,
        },
        {
            "schema_version": "semantic-audit-v1",
            "stats": {"error_count": 0, "warning_count": 2},
        },
        {
            "schema_version": "symbol-memory-summary-run-v1",
            "ended_ms": 2000,
            "high_risk_symbols": [
                {
                    "exchange": "binance",
                    "symbol": "ETHUSDT",
                    "contract_warning_count": 3,
                    "risk_score": 210.5,
                    "recent_contract_warning_types": ["state_features_semantic_contract_missing"],
                    "alert_codes": ["AGENT_ALTERNATIVE_SOURCES_CONFLICT"],
                },
                {
                    "exchange": "binance",
                    "symbol": "BTCUSDT",
                    "contract_warning_count": 2,
                    "risk_score": 120.0,
                    "recent_contract_warning_types": ["alternative_sources_conflict_detected"],
                }
            ],
        },
    ]
    out = build_summary(reports)
    assert out["report_count"] == 1
    assert out["semantic_audit_count"] == 1
    assert out["memory_summary_run_count"] == 1
    assert out["memory_high_risk_symbol_count"] == 2
    assert float(out["memory_top_risk_score"]) == 210.5
    rows = list(out.get("memory_high_risk_symbols") or [])
    assert rows and rows[0]["symbol"] == "ETHUSDT"
    assert out["memory_alert_code_count"] == 1
    top_codes = list(out.get("memory_top_alert_codes") or [])
    assert len(top_codes) == 1
    assert top_codes[0]["alert_code"] == "AGENT_ALTERNATIVE_SOURCES_CONFLICT"
    assert top_codes[0]["count"] == 2
    assert "binance:ETHUSDT" in list(top_codes[0]["symbols"] or [])
    assert "binance:BTCUSDT" in list(top_codes[0]["symbols"] or [])
