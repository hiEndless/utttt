#!/usr/bin/env bash
set -euo pipefail

OUT="verification/reports/quick.latest.json"
WITH_MEMORY_SUMMARY=0
WITH_AGENT_READYZ=0
WITH_DECISION_TRACE_SCHEMA_GUARD=0
WITH_PIPELINE_MODE_REPORT=0
WITH_EXECUTION_PROMPT_REPORT=0
WITH_EVENT_TYPE_MATCH_REPORT=0
SUMMARY_PATH="verification/reports/summary.latest.json"
MEMORY_SUMMARY_PATH="verification/reports/memory_summary.latest.json"
AGENT_READYZ_PATH="verification/reports/agent_readyz.latest.json"
DECISION_TRACE_SCHEMA_GUARD_PATH="verification/reports/agent_decision_trace_schema_guard.latest.json"
PIPELINE_MODE_REPORT_PATH="verification/reports/agent_pipeline_mode.latest.json"
EXECUTION_PROMPT_REPORT_PATH="verification/reports/execution_prompt_version.latest.json"
EVENT_TYPE_MATCH_REPORT_PATH="verification/reports/agent_event_type_match.latest.json"
AGENT_READYZ_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
COMPACT=1
SKIP_AGGREGATE=0

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/verify_quick_report.sh [options]

Options:
  --output <path>              quick suite 报告输出路径（默认 verification/reports/quick.latest.json）
  --with-memory-summary        quick 后聚合前生成 memory summary 报告
  --with-agent-readyz          quick 后聚合前生成 agent readyz 报告
  --with-decision-trace-schema-guard  quick 后聚合前生成 decision_trace schema guard 报告
  --with-pipeline-mode-report  quick 后聚合前生成 pipeline_mode 灰度报告
  --with-execution-prompt-report  quick 后聚合前生成 execution prompt 版本报告
  --with-event-type-match-report  quick 后聚合前生成 event_type 命中报告
  --summary-path <path>        聚合输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path> memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --agent-readyz-path <path>   agent readyz 输出路径（默认 verification/reports/agent_readyz.latest.json）
  --decision-trace-schema-guard-path <path> decision_trace schema guard 输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --pipeline-mode-report-path <path> pipeline_mode 输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --execution-prompt-report-path <path> execution prompt 输出路径（默认 verification/reports/execution_prompt_version.latest.json）
  --event-type-match-report-path <path> event_type 命中报告输出路径（默认 verification/reports/agent_event_type_match.latest.json）
  --agent-readyz-base-url <url> agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --no-compact                 聚合输出使用格式化 JSON（默认 compact）
  --skip-aggregate             仅生成 quick suite 报告，不执行聚合
  --help, -h                   显示帮助
USAGE
      exit 0
      ;;
    --output)
      OUT="${2:-$OUT}"
      shift 2
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
    --with-execution-prompt-report)
      WITH_EXECUTION_PROMPT_REPORT=1
      shift
      ;;
    --with-event-type-match-report)
      WITH_EVENT_TYPE_MATCH_REPORT=1
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
    --execution-prompt-report-path)
      EXECUTION_PROMPT_REPORT_PATH="${2:-$EXECUTION_PROMPT_REPORT_PATH}"
      shift 2
      ;;
    --event-type-match-report-path)
      EVENT_TYPE_MATCH_REPORT_PATH="${2:-$EVENT_TYPE_MATCH_REPORT_PATH}"
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
    --no-compact)
      COMPACT=0
      shift
      ;;
    --skip-aggregate)
      SKIP_AGGREGATE=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

bash verification/run_suite.sh --suite=quick --report-json="$OUT"
echo "[ok] report generated: $OUT"

if [[ "$SKIP_AGGREGATE" == "1" ]]; then
  exit 0
fi

AGG_ARGS=(--summary-path "$SUMMARY_PATH" --skip-thresholds)
if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  AGG_ARGS+=(--with-memory-summary --memory-summary-path "$MEMORY_SUMMARY_PATH")
fi
if [[ "$WITH_AGENT_READYZ" == "1" ]]; then
  AGG_ARGS+=(
    --with-agent-readyz
    --agent-readyz-path "$AGENT_READYZ_PATH"
    --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
    --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
  )
fi
if [[ "$WITH_DECISION_TRACE_SCHEMA_GUARD" == "1" ]]; then
  AGG_ARGS+=(
    --with-decision-trace-schema-guard
    --decision-trace-schema-guard-path "$DECISION_TRACE_SCHEMA_GUARD_PATH"
  )
fi
if [[ "$WITH_PIPELINE_MODE_REPORT" == "1" ]]; then
  AGG_ARGS+=(
    --with-pipeline-mode-report
    --pipeline-mode-report-path "$PIPELINE_MODE_REPORT_PATH"
  )
fi
if [[ "$WITH_EXECUTION_PROMPT_REPORT" == "1" ]]; then
  AGG_ARGS+=(
    --with-execution-prompt-report
    --execution-prompt-report-path "$EXECUTION_PROMPT_REPORT_PATH"
  )
fi
if [[ "$WITH_EVENT_TYPE_MATCH_REPORT" == "1" ]]; then
  AGG_ARGS+=(
    --with-event-type-match-report
    --event-type-match-report-path "$EVENT_TYPE_MATCH_REPORT_PATH"
  )
fi
if [[ "$COMPACT" == "1" ]]; then
  AGG_ARGS+=(--compact)
fi

bash tools/local/aggregate_and_check.sh "${AGG_ARGS[@]}"

if [[ "$WITH_PIPELINE_MODE_REPORT" == "1" ]]; then
  bash tools/local/print_pipeline_mode_summary.sh --summary "$SUMMARY_PATH" --prefix quick
fi
