#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
MEMORY_SUMMARY_PATH="verification/reports/memory_summary.latest.json"
AGENT_READYZ_PATH="verification/reports/agent_readyz.latest.json"
DECISION_TRACE_SCHEMA_GUARD_PATH="verification/reports/agent_decision_trace_schema_guard.latest.json"
PIPELINE_MODE_REPORT_PATH="verification/reports/agent_pipeline_mode.latest.json"
AGENT_READYZ_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
WITH_MEMORY_SUMMARY=0
WITH_AGENT_READYZ=0
WITH_DECISION_TRACE_SCHEMA_GUARD=0
WITH_PIPELINE_MODE_REPORT=0
SKIP_THRESHOLDS=0
COMPACT=0
MAX_LEGACY_CONFIDENCE_RATIO="-1"
MAX_AGENT_READYZ_LEVEL="red"
REQUIRE_AGENT_READYZ_REPORT=0
MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="-1"

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/aggregate_and_check.sh [options]

Options:
  --with-memory-summary         先生成 memory summary 再聚合
  --with-agent-readyz           先生成 agent readyz 报告再聚合
  --with-decision-trace-schema-guard  先生成 decision_trace schema guard 报告再聚合
  --with-pipeline-mode-report   先生成 pipeline_mode 灰度报告再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --agent-readyz-path <path>    agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --decision-trace-schema-guard-path <path>
                               decision_trace schema guard 报告输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --pipeline-mode-report-path <path>
                               pipeline_mode 报告输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --agent-readyz-base-url <url> agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --compact                     生成紧凑 JSON（透传给 aggregate_reports --compact）
  --skip-thresholds             仅聚合，不执行阈值检查
  --max-legacy-confidence-ratio <float>
                               execution legacy confidence 占比上限（默认 -1 忽略）
  --max-agent-readyz-level <green|yellow|red>
                               agent readyz 最大允许状态级别（默认 red）
  --max-decision-trace-schema-guard-invalid-records <int>
                               decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  --require-agent-readyz-report 要求存在 agent readyz 报告（默认关闭）
  --help, -h                    显示帮助
USAGE
      exit 0
      ;;
    --with-memory-summary)
      WITH_MEMORY_SUMMARY=1
      shift
      ;;
    --with-agent-readyz)
      WITH_AGENT_READYZ=1
      shift
      ;;
    --with-decision-trace-schema-guard)
      WITH_DECISION_TRACE_SCHEMA_GUARD=1
      shift
      ;;
    --with-pipeline-mode-report)
      WITH_PIPELINE_MODE_REPORT=1
      shift
      ;;
    --summary-path)
      SUMMARY_PATH="${2:-$SUMMARY_PATH}"
      shift 2
      ;;
    --memory-summary-path)
      MEMORY_SUMMARY_PATH="${2:-$MEMORY_SUMMARY_PATH}"
      shift 2
      ;;
    --agent-readyz-path)
      AGENT_READYZ_PATH="${2:-$AGENT_READYZ_PATH}"
      shift 2
      ;;
    --decision-trace-schema-guard-path)
      DECISION_TRACE_SCHEMA_GUARD_PATH="${2:-$DECISION_TRACE_SCHEMA_GUARD_PATH}"
      shift 2
      ;;
    --pipeline-mode-report-path)
      PIPELINE_MODE_REPORT_PATH="${2:-$PIPELINE_MODE_REPORT_PATH}"
      shift 2
      ;;
    --agent-readyz-base-url)
      AGENT_READYZ_BASE_URL="${2:-$AGENT_READYZ_BASE_URL}"
      shift 2
      ;;
    --agent-readyz-timeout-s)
      AGENT_READYZ_TIMEOUT_S="${2:-$AGENT_READYZ_TIMEOUT_S}"
      shift 2
      ;;
    --skip-thresholds)
      SKIP_THRESHOLDS=1
      shift
      ;;
    --compact)
      COMPACT=1
      shift
      ;;
    --max-legacy-confidence-ratio)
      MAX_LEGACY_CONFIDENCE_RATIO="${2:-$MAX_LEGACY_CONFIDENCE_RATIO}"
      shift 2
      ;;
    --max-agent-readyz-level)
      MAX_AGENT_READYZ_LEVEL="${2:-$MAX_AGENT_READYZ_LEVEL}"
      shift 2
      ;;
    --max-decision-trace-schema-guard-invalid-records)
      MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${2:-$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS}"
      shift 2
      ;;
    --require-agent-readyz-report)
      REQUIRE_AGENT_READYZ_REPORT=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

AGGREGATE_ARGS=(--glob 'verification/reports/*.json' --output "$SUMMARY_PATH")
if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  AGGREGATE_ARGS+=(--with-memory-summary --memory-summary-path "$MEMORY_SUMMARY_PATH")
fi
if [[ "$WITH_AGENT_READYZ" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-agent-readyz
    --agent-readyz-path "$AGENT_READYZ_PATH"
    --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
    --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
  )
fi
if [[ "$WITH_DECISION_TRACE_SCHEMA_GUARD" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-decision-trace-schema-guard
    --decision-trace-schema-guard-path "$DECISION_TRACE_SCHEMA_GUARD_PATH"
  )
fi
if [[ "$WITH_PIPELINE_MODE_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-pipeline-mode-report
    --pipeline-mode-report-path "$PIPELINE_MODE_REPORT_PATH"
  )
fi
if [[ "$COMPACT" == "1" ]]; then
  AGGREGATE_ARGS+=(--compact)
fi
bash tools/local/verify_report_aggregate.sh "${AGGREGATE_ARGS[@]}"
if [[ "$SKIP_THRESHOLDS" == "0" ]]; then
  THRESHOLD_ARGS=(
    --summary "$SUMMARY_PATH"
    --min-pass-rate 1.0
    --max-failed 0
    --min-reports 1
    --max-semantic-errors 0
    --max-legacy-confidence-ratio "$MAX_LEGACY_CONFIDENCE_RATIO"
    --max-agent-readyz-level "$MAX_AGENT_READYZ_LEVEL"
    --max-decision-trace-schema-guard-invalid-records "$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
  )
  if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
    THRESHOLD_ARGS+=(--require-agent-readyz-report)
  fi
  python3 -m verification.reports.check_thresholds \
    "${THRESHOLD_ARGS[@]}"
fi
