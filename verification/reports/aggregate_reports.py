from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List


_WARNING_TO_ALERT_CODE = {
    "alternative_sources_conflict_detected": "AGENT_ALTERNATIVE_SOURCES_CONFLICT",
    "state_features_alternative_source_provider_state_invalid": "AGENT_ALTERNATIVE_SOURCES_PROVIDER_STATE_INVALID",
}


def _load_reports(pattern: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        p = Path(path)
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            schema_version = str(data.get("schema_version") or "").strip()
            if schema_version not in {
                "verification-report-v1",
                "verification-report-v2",
                "semantic-audit-v1",
                "symbol-memory-summary-run-v1",
                "execution-confidence-metrics-v1",
                "execution-prompt-version-report-v1",
                "agent-readyz-report-v1",
                "agent-decision-trace-schema-guard-report-v1",
                "agent-pipeline-mode-report-v1",
            } and "confidence_migration_metrics" not in data:
                continue
            data["_path"] = str(p)
            out.append(data)
    return out


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _collect_symbol_alert_codes(item: Dict[str, Any]) -> List[str]:
    codes: List[str] = []
    for key in ("alert_codes", "recent_alert_codes"):
        raw = item.get(key)
        if isinstance(raw, list):
            for x in raw:
                code = str(x or "").strip()
                if code:
                    codes.append(code)
    warnings = item.get("recent_contract_warning_types")
    if isinstance(warnings, list):
        for x in warnings:
            warn = str(x or "").strip()
            if not warn:
                continue
            code = _WARNING_TO_ALERT_CODE.get(warn)
            if code:
                codes.append(code)
    return sorted(set(codes))


def build_summary(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    verification_reports = [
        x for x in reports if str(x.get("schema_version") or "") in {"verification-report-v1", "verification-report-v2"}
    ]
    semantic_reports = [x for x in reports if str(x.get("schema_version") or "") == "semantic-audit-v1"]
    memory_summary_reports = [x for x in reports if str(x.get("schema_version") or "") == "symbol-memory-summary-run-v1"]
    execution_confidence_reports = [
        x
        for x in reports
        if (
            str(x.get("schema_version") or "") == "execution-confidence-metrics-v1"
            or isinstance(x.get("confidence_migration_metrics"), dict)
        )
    ]
    execution_prompt_reports = [
        x for x in reports if str(x.get("schema_version") or "") == "execution-prompt-version-report-v1"
    ]
    agent_readyz_reports = [x for x in reports if str(x.get("schema_version") or "") == "agent-readyz-report-v1"]
    decision_trace_schema_guard_reports = [
        x for x in reports if str(x.get("schema_version") or "") == "agent-decision-trace-schema-guard-report-v1"
    ]
    pipeline_mode_reports = [x for x in reports if str(x.get("schema_version") or "") == "agent-pipeline-mode-report-v1"]

    total = len(verification_reports)
    passed = 0
    failed = 0
    duration_sum = 0
    latest_finished = 0
    by_suite: Dict[str, Dict[str, Any]] = {}

    for item in verification_reports:
        suite = str(item.get("suite") or "unknown")
        status = str(item.get("status") or "unknown")
        duration_ms = _to_int(item.get("duration_ms"), 0)
        finished_at_ms = _to_int(item.get("finished_at_ms"), 0)

        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1

        duration_sum += max(0, duration_ms)
        latest_finished = max(latest_finished, finished_at_ms)

        slot = by_suite.setdefault(
            suite,
            {
                "suite": suite,
                "count": 0,
                "passed": 0,
                "failed": 0,
                "avg_duration_ms": 0,
                "latest_finished_at_ms": 0,
            },
        )
        slot["count"] += 1
        if status == "passed":
            slot["passed"] += 1
        elif status == "failed":
            slot["failed"] += 1
        slot["avg_duration_ms"] += max(0, duration_ms)
        slot["latest_finished_at_ms"] = max(_to_int(slot.get("latest_finished_at_ms"), 0), finished_at_ms)

    suites = []
    for suite in sorted(by_suite.keys()):
        item = dict(by_suite[suite])
        count = max(1, _to_int(item.get("count"), 1))
        item["avg_duration_ms"] = int(_to_int(item.get("avg_duration_ms"), 0) / count)
        suites.append(item)

    pass_rate = 0.0 if total <= 0 else round(float(passed) / float(total), 6)
    avg_duration = 0 if total <= 0 else int(duration_sum / total)

    semantic_error_count = 0
    semantic_warning_count = 0
    latest_semantic_report_path = ""
    if semantic_reports:
        latest_semantic = semantic_reports[-1]
        stats = latest_semantic.get("stats") if isinstance(latest_semantic.get("stats"), dict) else {}
        semantic_error_count = _to_int(stats.get("error_count"), 0)
        semantic_warning_count = _to_int(stats.get("warning_count"), 0)
        latest_semantic_report_path = str(latest_semantic.get("_path") or "")

    latest_memory_summary_report_path = ""
    memory_high_risk_symbols: List[Dict[str, Any]] = []
    memory_high_risk_symbol_count = 0
    memory_top_risk_score = 0.0
    memory_alert_codes: Dict[str, Dict[str, Any]] = {}
    if memory_summary_reports:
        latest_memory_summary = max(memory_summary_reports, key=lambda x: _to_int(x.get("ended_ms"), 0))
        latest_memory_summary_report_path = str(latest_memory_summary.get("_path") or "")
        memory_high_risk_symbols = [
            dict(x) for x in list(latest_memory_summary.get("high_risk_symbols") or []) if isinstance(x, dict)
        ]
        memory_high_risk_symbol_count = len(memory_high_risk_symbols)
        if memory_high_risk_symbols:
            memory_top_risk_score = max(
                [
                    float(item.get("risk_score") or 0.0)
                    for item in memory_high_risk_symbols
                    if isinstance(item, dict)
                ]
                or [0.0]
            )
            for row in memory_high_risk_symbols:
                exchange = str(row.get("exchange") or "").strip().lower()
                symbol = str(row.get("symbol") or "").strip().upper()
                symbol_key = f"{exchange}:{symbol}" if exchange and symbol else symbol or exchange
                if not symbol_key:
                    continue
                for code in _collect_symbol_alert_codes(row):
                    slot = memory_alert_codes.setdefault(code, {"count": 0, "symbols": set()})
                    slot["count"] = int(slot.get("count") or 0) + 1
                    slot["symbols"].add(symbol_key)

    memory_top_alert_codes = []
    for code, payload in sorted(
        memory_alert_codes.items(),
        key=lambda kv: (-int(kv[1].get("count") or 0), kv[0]),
    ):
        symbols = sorted([str(x) for x in list(payload.get("symbols") or []) if str(x).strip()])
        memory_top_alert_codes.append(
            {
                "alert_code": code,
                "count": int(payload.get("count") or 0),
                "symbols": symbols,
                "symbol_count": len(symbols),
            }
        )

    execution_confidence_report_count = len(execution_confidence_reports)
    latest_execution_confidence_report_path = ""
    execution_confidence_only_requests = 0
    execution_decision_confidence_requests = 0
    execution_confidence_alias_mismatch_rejections = 0
    execution_legacy_confidence_usage_ratio = 0.0
    if execution_confidence_reports:
        latest_execution_confidence = max(
            execution_confidence_reports,
            key=lambda x: max(
                _to_int(x.get("ts_ms"), 0),
                _to_int(x.get("ts"), 0),
                _to_int(x.get("finished_at_ms"), 0),
            ),
        )
        latest_execution_confidence_report_path = str(latest_execution_confidence.get("_path") or "")
        metrics = dict(latest_execution_confidence.get("confidence_migration_metrics") or {})
        execution_confidence_only_requests = _to_int(metrics.get("confidence_only_requests"), 0)
        execution_decision_confidence_requests = _to_int(metrics.get("decision_confidence_requests"), 0)
        execution_confidence_alias_mismatch_rejections = _to_int(
            metrics.get("confidence_alias_mismatch_rejections"), 0
        )
        denom = execution_confidence_only_requests + execution_decision_confidence_requests
        execution_legacy_confidence_usage_ratio = 0.0 if denom <= 0 else round(
            float(execution_confidence_only_requests) / float(denom), 6
        )

    execution_prompt_report_count = len(execution_prompt_reports)
    latest_execution_prompt_report_path = ""
    execution_prompt_tracked_requests_total = 0
    execution_prompt_version_count = 0
    execution_prompt_tracking_coverage_ratio = 0.0
    execution_prompt_top_versions: List[Dict[str, Any]] = []
    if execution_prompt_reports:
        latest_execution_prompt = max(
            execution_prompt_reports,
            key=lambda x: max(
                _to_int(x.get("generated_at_ms"), 0),
                _to_int(x.get("ts_ms"), 0),
                _to_int(x.get("ts"), 0),
            ),
        )
        latest_execution_prompt_report_path = str(latest_execution_prompt.get("_path") or "")
        summary = dict(latest_execution_prompt.get("summary") or {})
        execution_prompt_tracked_requests_total = _to_int(summary.get("tracked_prompt_requests_total"), 0)
        execution_prompt_version_count = _to_int(summary.get("prompt_version_count"), 0)
        try:
            execution_prompt_tracking_coverage_ratio = round(float(summary.get("tracking_coverage_ratio") or 0.0), 6)
        except Exception:
            execution_prompt_tracking_coverage_ratio = 0.0
        rows = [dict(x) for x in list(latest_execution_prompt.get("versions") or []) if isinstance(x, dict)]
        rows_sorted = sorted(
            rows,
            key=lambda x: (-_to_int(x.get("count"), 0), str(x.get("prompt_config_version") or "")),
        )
        execution_prompt_top_versions = rows_sorted[:5]

    agent_readyz_report_count = len(agent_readyz_reports)
    latest_agent_readyz_report_path = ""
    agent_readyz_ok = False
    agent_readyz_status_level = "red"
    agent_readyz_warning_count = 0
    agent_readyz_error_count = 0
    agent_readyz_errors: List[str] = []
    if agent_readyz_reports:
        latest_agent_readyz = max(
            agent_readyz_reports,
            key=lambda x: max(
                _to_int(x.get("collected_at_ms"), 0),
                _to_int(x.get("ts_ms"), 0),
                _to_int(x.get("ts"), 0),
            ),
        )
        latest_agent_readyz_report_path = str(latest_agent_readyz.get("_path") or "")
        agent_readyz_ok = bool(latest_agent_readyz.get("ok"))
        level = str(latest_agent_readyz.get("status_level") or "").strip().lower()
        agent_readyz_status_level = level if level in {"green", "yellow", "red"} else ("green" if agent_readyz_ok else "red")
        warnings = latest_agent_readyz.get("warnings")
        errors = latest_agent_readyz.get("errors")
        if isinstance(warnings, list):
            agent_readyz_warning_count = len([x for x in warnings if str(x or "").strip()])
        if isinstance(errors, list):
            normalized_errors = [str(x or "").strip() for x in errors if str(x or "").strip()]
            agent_readyz_error_count = len(normalized_errors)
            agent_readyz_errors = sorted(set(normalized_errors))

    decision_trace_schema_guard_report_count = len(decision_trace_schema_guard_reports)
    latest_decision_trace_schema_guard_report_path = ""
    decision_trace_schema_guard_invalid_records = 0
    decision_trace_schema_guard_affected_event_count = 0
    if decision_trace_schema_guard_reports:
        latest_dt_guard = max(
            decision_trace_schema_guard_reports,
            key=lambda x: max(
                _to_int(x.get("generated_at_ms"), 0),
                _to_int(x.get("ts_ms"), 0),
                _to_int(x.get("ts"), 0),
            ),
        )
        latest_decision_trace_schema_guard_report_path = str(latest_dt_guard.get("_path") or "")
        summary = dict(latest_dt_guard.get("summary") or {})
        decision_trace_schema_guard_invalid_records = _to_int(summary.get("invalid_guard_records"), 0)
        decision_trace_schema_guard_affected_event_count = _to_int(summary.get("affected_event_count"), 0)

    pipeline_mode_report_count = len(pipeline_mode_reports)
    latest_pipeline_mode_report_path = ""
    pipeline_mode_legacy_count = 0
    pipeline_mode_minimal_count = 0
    pipeline_mode_unknown_count = 0
    pipeline_mode_missing_count = 0
    pipeline_mode_legacy_ratio = 0.0
    pipeline_mode_minimal_ratio = 0.0
    if pipeline_mode_reports:
        latest_pipeline_mode = max(
            pipeline_mode_reports,
            key=lambda x: max(
                _to_int(x.get("generated_at_ms"), 0),
                _to_int(x.get("ts_ms"), 0),
                _to_int(x.get("ts"), 0),
            ),
        )
        latest_pipeline_mode_report_path = str(latest_pipeline_mode.get("_path") or "")
        summary = dict(latest_pipeline_mode.get("summary") or {})
        pipeline_mode_legacy_count = _to_int(summary.get("legacy_count"), 0)
        pipeline_mode_minimal_count = _to_int(summary.get("minimal_count"), 0)
        pipeline_mode_unknown_count = _to_int(summary.get("unknown_count"), 0)
        pipeline_mode_missing_count = _to_int(summary.get("missing_pipeline_mode_count"), 0)
        try:
            pipeline_mode_legacy_ratio = round(float(summary.get("legacy_ratio") or 0.0), 6)
        except Exception:
            pipeline_mode_legacy_ratio = 0.0
        try:
            pipeline_mode_minimal_ratio = round(float(summary.get("minimal_ratio") or 0.0), 6)
        except Exception:
            pipeline_mode_minimal_ratio = 0.0

    return {
        "schema_version": "verification-report-aggregate-v1",
        "verification_report_count": total,
        "report_count": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "avg_duration_ms": avg_duration,
        "latest_finished_at_ms": latest_finished,
        "suites": suites,
        "semantic_audit_count": len(semantic_reports),
        "semantic_error_count": semantic_error_count,
        "semantic_warning_count": semantic_warning_count,
        "latest_semantic_report_path": latest_semantic_report_path,
        "memory_summary_run_count": len(memory_summary_reports),
        "latest_memory_summary_report_path": latest_memory_summary_report_path,
        "memory_high_risk_symbol_count": memory_high_risk_symbol_count,
        "memory_top_risk_score": round(float(memory_top_risk_score), 6),
        "memory_high_risk_symbols": memory_high_risk_symbols,
        "memory_alert_code_count": len(memory_top_alert_codes),
        "memory_top_alert_codes": memory_top_alert_codes,
        "execution_confidence_report_count": execution_confidence_report_count,
        "latest_execution_confidence_report_path": latest_execution_confidence_report_path,
        "execution_confidence_only_requests": execution_confidence_only_requests,
        "execution_decision_confidence_requests": execution_decision_confidence_requests,
        "execution_confidence_alias_mismatch_rejections": execution_confidence_alias_mismatch_rejections,
        "execution_legacy_confidence_usage_ratio": execution_legacy_confidence_usage_ratio,
        "execution_prompt_report_count": execution_prompt_report_count,
        "latest_execution_prompt_report_path": latest_execution_prompt_report_path,
        "execution_prompt_tracked_requests_total": execution_prompt_tracked_requests_total,
        "execution_prompt_version_count": execution_prompt_version_count,
        "execution_prompt_tracking_coverage_ratio": execution_prompt_tracking_coverage_ratio,
        "execution_prompt_top_versions": execution_prompt_top_versions,
        "agent_readyz_report_count": agent_readyz_report_count,
        "latest_agent_readyz_report_path": latest_agent_readyz_report_path,
        "agent_readyz_ok": agent_readyz_ok,
        "agent_readyz_status_level": agent_readyz_status_level,
        "agent_readyz_warning_count": agent_readyz_warning_count,
        "agent_readyz_error_count": agent_readyz_error_count,
        "agent_readyz_errors": agent_readyz_errors,
        "decision_trace_schema_guard_report_count": decision_trace_schema_guard_report_count,
        "latest_decision_trace_schema_guard_report_path": latest_decision_trace_schema_guard_report_path,
        "decision_trace_schema_guard_invalid_records": decision_trace_schema_guard_invalid_records,
        "decision_trace_schema_guard_affected_event_count": decision_trace_schema_guard_affected_event_count,
        "pipeline_mode_report_count": pipeline_mode_report_count,
        "latest_pipeline_mode_report_path": latest_pipeline_mode_report_path,
        "pipeline_mode_legacy_count": pipeline_mode_legacy_count,
        "pipeline_mode_minimal_count": pipeline_mode_minimal_count,
        "pipeline_mode_unknown_count": pipeline_mode_unknown_count,
        "pipeline_mode_missing_count": pipeline_mode_missing_count,
        "pipeline_mode_legacy_ratio": pipeline_mode_legacy_ratio,
        "pipeline_mode_minimal_ratio": pipeline_mode_minimal_ratio,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="聚合 verification 报告")
    p.add_argument("--glob", default="verification/reports/*.json", help="报告文件 glob")
    p.add_argument("--output", default="", help="可选：写入输出文件")
    p.add_argument("--compact", action="store_true", help="紧凑 JSON 输出")
    return p


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    reports = _load_reports(str(args.glob))
    summary = build_summary(reports)
    rendered = json.dumps(summary, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2)
    print(rendered)

    output = str(args.output or "").strip()
    if output:
        p = Path(output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
