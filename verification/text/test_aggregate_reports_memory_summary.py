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
                    "recent_contract_warning_types": [
                        "alternative_sources_conflict_detected",
                        "state_features_alternative_source_provider_state_invalid",
                    ],
                }
            ],
        },
        {
            "schema_version": "execution-confidence-metrics-v1",
            "ts_ms": 3000,
            "confidence_migration_metrics": {
                "decide_requests_total": 10,
                "confidence_only_requests": 2,
                "decision_confidence_requests": 8,
                "confidence_alias_mismatch_rejections": 1,
            },
        },
        {
            "schema_version": "agent-readyz-report-v1",
            "collected_at_ms": 3500,
            "ok": False,
            "status_level": "red",
            "runtime_profile": "prod",
            "warnings": ["market_state_unreachable"],
            "errors": ["event_recorder_low_disk", "market_state_unreachable"],
            "checks": {"market_state_healthz": {"ok": False}},
        },
        {
            "schema_version": "agent-decision-trace-schema-guard-report-v1",
            "generated_at_ms": 3600,
            "summary": {
                "total_guard_records": 4,
                "invalid_guard_records": 2,
                "affected_event_count": 1,
            },
            "events": [
                {"event_id": "evt-1", "hits": 2, "max_error_count": 3}
            ],
        },
        {
            "schema_version": "agent-pipeline-mode-report-v1",
            "generated_at_ms": 3700,
            "summary": {
                "decision_trace_record_count": 10,
                "decision_trace_event_count": 6,
                "legacy_count": 4,
                "minimal_count": 5,
                "unknown_count": 1,
                "missing_pipeline_mode_count": 0,
                "legacy_ratio": 0.444444,
                "minimal_ratio": 0.555556,
            },
            "unknown_samples": [{"event_id": "evt-x", "pipeline_mode": "future_mode", "ts_ms": 1700000000000}],
        },
        {
            "schema_version": "agent-event-type-match-report-v1",
            "generated_at_ms": 3800,
            "summary": {
                "decision_trace_record_count": 10,
                "decision_trace_event_count": 6,
                "match_mode_canonical_or_raw_count": 6,
                "match_mode_alias_count": 3,
                "match_mode_empty_count": 1,
                "match_mode_unknown_count": 0,
                "missing_match_mode_count": 0,
                "match_mode_alias_ratio": 0.3,
                "match_mode_canonical_or_raw_ratio": 0.6,
            },
            "top_unknown_event_types": [
                {"event_type_raw": "my_custom_event", "count": 4},
                {"event_type_raw": "foo_signal", "count": 2},
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
    assert out["memory_alert_code_count"] == 2
    top_codes = list(out.get("memory_top_alert_codes") or [])
    assert len(top_codes) == 2
    by_code = {str(item.get("alert_code")): item for item in top_codes}
    conflict = dict(by_code.get("AGENT_ALTERNATIVE_SOURCES_CONFLICT") or {})
    invalid_state = dict(by_code.get("AGENT_ALTERNATIVE_SOURCES_PROVIDER_STATE_INVALID") or {})
    assert conflict.get("count") == 2
    assert "binance:ETHUSDT" in list(conflict.get("symbols") or [])
    assert "binance:BTCUSDT" in list(conflict.get("symbols") or [])
    assert invalid_state.get("count") == 1
    assert "binance:BTCUSDT" in list(invalid_state.get("symbols") or [])
    assert out["execution_confidence_report_count"] == 1
    assert out["execution_confidence_only_requests"] == 2
    assert out["execution_decision_confidence_requests"] == 8
    assert out["execution_confidence_alias_mismatch_rejections"] == 1
    assert float(out["execution_legacy_confidence_usage_ratio"]) == 0.2
    assert out["agent_readyz_report_count"] == 1
    assert out["agent_readyz_ok"] is False
    assert out["agent_readyz_status_level"] == "red"
    assert out["agent_readyz_warning_count"] == 1
    assert out["agent_readyz_error_count"] == 2
    assert out["agent_readyz_errors"] == ["event_recorder_low_disk", "market_state_unreachable"]
    assert out["decision_trace_schema_guard_report_count"] == 1
    assert out["decision_trace_schema_guard_invalid_records"] == 2
    assert out["decision_trace_schema_guard_affected_event_count"] == 1
    assert out["pipeline_mode_report_count"] == 1
    assert out["pipeline_mode_legacy_count"] == 4
    assert out["pipeline_mode_minimal_count"] == 5
    assert out["pipeline_mode_unknown_count"] == 1
    assert out["pipeline_mode_missing_count"] == 0
    assert float(out["pipeline_mode_legacy_ratio"]) == 0.444444
    assert float(out["pipeline_mode_minimal_ratio"]) == 0.555556
    assert out["event_type_match_report_count"] == 1
    assert out["event_type_match_alias_count"] == 3
    assert out["event_type_match_canonical_or_raw_count"] == 6
    assert out["event_type_match_empty_count"] == 1
    assert out["event_type_match_unknown_count"] == 0
    assert out["event_type_match_missing_count"] == 0
    assert float(out["event_type_match_alias_ratio"]) == 0.3
    assert float(out["event_type_match_canonical_or_raw_ratio"]) == 0.6
    top_unknown = list(out.get("event_type_match_top_unknown_event_types") or [])
    assert top_unknown
    assert top_unknown[0]["event_type_raw"] == "my_custom_event"
    assert top_unknown[0]["count"] == 4
