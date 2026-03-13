from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


_LEVEL_ORDER = {"green": 0, "yellow": 1, "red": 2}


def _load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="检查 verification 聚合报告阈值")
    p.add_argument("--summary", default="verification/reports/summary.latest.json", help="聚合报告路径")
    p.add_argument("--min-pass-rate", type=float, default=1.0, help="最低通过率")
    p.add_argument("--max-failed", type=int, default=0, help="最大失败报告数")
    p.add_argument("--min-reports", type=int, default=1, help="最小报告数")
    p.add_argument("--max-semantic-errors", type=int, default=0, help="最大语义审计错误数")
    p.add_argument("--max-semantic-warnings", type=int, default=-1, help="最大语义审计告警数，-1 表示忽略")
    p.add_argument(
        "--max-legacy-confidence-ratio",
        type=float,
        default=-1.0,
        help="最大 execution legacy confidence 使用占比，-1 表示忽略",
    )
    p.add_argument(
        "--max-agent-readyz-level",
        choices=["green", "yellow", "red"],
        default="red",
        help="允许的最大 agent readyz 状态级别（green<yellow<red，默认 red）",
    )
    p.add_argument(
        "--max-decision-trace-schema-guard-invalid-records",
        type=int,
        default=-1,
        help="最大 decision_trace schema guard invalid 记录数，-1 表示忽略",
    )
    p.add_argument(
        "--max-pipeline-mode-unknown-count",
        type=int,
        default=-1,
        help="最大 pipeline_mode unknown 计数，-1 表示忽略",
    )
    p.add_argument(
        "--max-pipeline-mode-missing-count",
        type=int,
        default=-1,
        help="最大 pipeline_mode 缺失计数，-1 表示忽略",
    )
    p.add_argument(
        "--max-event-type-match-missing-count",
        type=int,
        default=-1,
        help="最大 event_type_match 缺失计数，-1 表示忽略",
    )
    p.add_argument(
        "--max-event-type-match-unknown-count",
        type=int,
        default=-1,
        help="最大 event_type_match unknown 计数，-1 表示忽略",
    )
    p.add_argument(
        "--min-event-type-match-alias-ratio",
        type=float,
        default=-1.0,
        help="最小 event_type_match alias 占比，-1 表示忽略",
    )
    p.add_argument(
        "--require-agent-readyz-report",
        action="store_true",
        help="要求 summary 中存在 agent readyz 报告（agent_readyz_report_count > 0）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = _load_json(str(args.summary))

    report_count = _to_int(summary.get("report_count"), 0)
    failed = _to_int(summary.get("failed"), 0)
    pass_rate = _to_float(summary.get("pass_rate"), 0.0)
    semantic_errors = _to_int(summary.get("semantic_error_count"), 0)
    semantic_warnings = _to_int(summary.get("semantic_warning_count"), 0)
    legacy_confidence_ratio = _to_float(summary.get("execution_legacy_confidence_usage_ratio"), 0.0)
    agent_readyz_report_count = _to_int(summary.get("agent_readyz_report_count"), 0)
    agent_readyz_level = str(summary.get("agent_readyz_status_level") or "red").strip().lower()
    decision_trace_schema_guard_invalid_records = _to_int(
        summary.get("decision_trace_schema_guard_invalid_records"), 0
    )
    pipeline_mode_unknown_count = _to_int(summary.get("pipeline_mode_unknown_count"), 0)
    pipeline_mode_missing_count = _to_int(summary.get("pipeline_mode_missing_count"), 0)
    event_type_match_missing_count = _to_int(summary.get("event_type_match_missing_count"), 0)
    event_type_match_unknown_count = _to_int(summary.get("event_type_match_unknown_count"), 0)
    event_type_match_alias_ratio = _to_float(summary.get("event_type_match_alias_ratio"), 0.0)
    if agent_readyz_level not in _LEVEL_ORDER:
        agent_readyz_level = "red"

    errors = []
    if report_count < int(args.min_reports):
        errors.append(f"report_count<{int(args.min_reports)} (actual={report_count})")
    if failed > int(args.max_failed):
        errors.append(f"failed>{int(args.max_failed)} (actual={failed})")
    if pass_rate < float(args.min_pass_rate):
        errors.append(f"pass_rate<{float(args.min_pass_rate)} (actual={pass_rate})")
    if semantic_errors > int(args.max_semantic_errors):
        errors.append(f"semantic_error_count>{int(args.max_semantic_errors)} (actual={semantic_errors})")
    if int(args.max_semantic_warnings) >= 0 and semantic_warnings > int(args.max_semantic_warnings):
        errors.append(f"semantic_warning_count>{int(args.max_semantic_warnings)} (actual={semantic_warnings})")
    if float(args.max_legacy_confidence_ratio) >= 0 and legacy_confidence_ratio > float(args.max_legacy_confidence_ratio):
        errors.append(
            "execution_legacy_confidence_usage_ratio>"
            f"{float(args.max_legacy_confidence_ratio)} (actual={legacy_confidence_ratio})"
        )
    if bool(args.require_agent_readyz_report) and agent_readyz_report_count <= 0:
        errors.append("agent_readyz_report_count<=0 (required)")
    if agent_readyz_report_count > 0:
        max_level = str(args.max_agent_readyz_level).strip().lower()
        if _LEVEL_ORDER.get(agent_readyz_level, 2) > _LEVEL_ORDER.get(max_level, 2):
            errors.append(f"agent_readyz_status_level>{max_level} (actual={agent_readyz_level})")
    if (
        int(args.max_decision_trace_schema_guard_invalid_records) >= 0
        and decision_trace_schema_guard_invalid_records > int(args.max_decision_trace_schema_guard_invalid_records)
    ):
        errors.append(
            "decision_trace_schema_guard_invalid_records>"
            f"{int(args.max_decision_trace_schema_guard_invalid_records)} "
            f"(actual={decision_trace_schema_guard_invalid_records})"
        )
    if int(args.max_pipeline_mode_unknown_count) >= 0 and pipeline_mode_unknown_count > int(
        args.max_pipeline_mode_unknown_count
    ):
        errors.append(
            "pipeline_mode_unknown_count>"
            f"{int(args.max_pipeline_mode_unknown_count)} "
            f"(actual={pipeline_mode_unknown_count})"
        )
    if int(args.max_pipeline_mode_missing_count) >= 0 and pipeline_mode_missing_count > int(
        args.max_pipeline_mode_missing_count
    ):
        errors.append(
            "pipeline_mode_missing_count>"
            f"{int(args.max_pipeline_mode_missing_count)} "
            f"(actual={pipeline_mode_missing_count})"
        )
    if int(args.max_event_type_match_missing_count) >= 0 and event_type_match_missing_count > int(
        args.max_event_type_match_missing_count
    ):
        errors.append(
            "event_type_match_missing_count>"
            f"{int(args.max_event_type_match_missing_count)} "
            f"(actual={event_type_match_missing_count})"
        )
    if int(args.max_event_type_match_unknown_count) >= 0 and event_type_match_unknown_count > int(
        args.max_event_type_match_unknown_count
    ):
        errors.append(
            "event_type_match_unknown_count>"
            f"{int(args.max_event_type_match_unknown_count)} "
            f"(actual={event_type_match_unknown_count})"
        )
    if float(args.min_event_type_match_alias_ratio) >= 0 and event_type_match_alias_ratio < float(
        args.min_event_type_match_alias_ratio
    ):
        errors.append(
            "event_type_match_alias_ratio<"
            f"{float(args.min_event_type_match_alias_ratio)} "
            f"(actual={event_type_match_alias_ratio})"
        )

    if errors:
        print("[failed] verification thresholds not satisfied")
        for item in errors:
            print(f"- {item}")
        return 1

    print("[passed] verification thresholds satisfied")
    print(
        f"report_count={report_count} failed={failed} pass_rate={pass_rate} "
        f"semantic_error_count={semantic_errors} semantic_warning_count={semantic_warnings} "
        f"execution_legacy_confidence_usage_ratio={legacy_confidence_ratio} "
        f"agent_readyz_report_count={agent_readyz_report_count} "
        f"agent_readyz_status_level={agent_readyz_level} "
        f"decision_trace_schema_guard_invalid_records={decision_trace_schema_guard_invalid_records} "
        f"pipeline_mode_unknown_count={pipeline_mode_unknown_count} "
        f"pipeline_mode_missing_count={pipeline_mode_missing_count} "
        f"event_type_match_missing_count={event_type_match_missing_count} "
        f"event_type_match_unknown_count={event_type_match_unknown_count} "
        f"event_type_match_alias_ratio={event_type_match_alias_ratio}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
