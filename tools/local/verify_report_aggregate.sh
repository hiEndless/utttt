#!/usr/bin/env bash
set -euo pipefail

GLOB='verification/reports/*.json'
OUT='verification/reports/summary.latest.json'
MEMORY_SUMMARY_PATH='verification/reports/memory_summary.latest.json'
AGENT_READYZ_PATH='verification/reports/agent_readyz.latest.json'
DECISION_TRACE_SCHEMA_GUARD_PATH='verification/reports/agent_decision_trace_schema_guard.latest.json'
AGENT_READYZ_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
COMPACT=0
WITH_MEMORY_SUMMARY=0
WITH_AGENT_READYZ=0
WITH_DECISION_TRACE_SCHEMA_GUARD=0
EXTRA_ARGS=()

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/verify_report_aggregate.sh [options]

Options:
  --glob <pattern>             聚合输入 glob（默认 verification/reports/*.json）
  --output <path>              聚合输出路径（默认 verification/reports/summary.latest.json）
  --compact                    生成紧凑 JSON
  --with-memory-summary        聚合前先生成 memory summary 报告
  --memory-summary-path <path> memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --with-agent-readyz          聚合前先生成 agent readyz 报告
  --agent-readyz-path <path>   agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --with-decision-trace-schema-guard  聚合前先生成 decision_trace schema guard 报告
  --decision-trace-schema-guard-path <path> decision_trace schema guard 输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --agent-readyz-base-url <url>  agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --help, -h                   显示帮助
USAGE
      exit 0
      ;;
    --glob)
      GLOB="${2:-$GLOB}"
      shift 2
      ;;
    --output)
      OUT="${2:-$OUT}"
      shift 2
      ;;
    --compact)
      COMPACT=1
      shift
      ;;
    --with-memory-summary)
      WITH_MEMORY_SUMMARY=1
      shift
      ;;
    --memory-summary-path)
      MEMORY_SUMMARY_PATH="${2:-$MEMORY_SUMMARY_PATH}"
      shift 2
      ;;
    --with-agent-readyz)
      WITH_AGENT_READYZ=1
      shift
      ;;
    --with-decision-trace-schema-guard)
      WITH_DECISION_TRACE_SCHEMA_GUARD=1
      shift
      ;;
    --decision-trace-schema-guard-path)
      DECISION_TRACE_SCHEMA_GUARD_PATH="${2:-$DECISION_TRACE_SCHEMA_GUARD_PATH}"
      shift 2
      ;;
    --agent-readyz-path)
      AGENT_READYZ_PATH="${2:-$AGENT_READYZ_PATH}"
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
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  bash tools/local/run_agent_memory_summary_report.sh "$MEMORY_SUMMARY_PATH"
fi
if [[ "$WITH_AGENT_READYZ" == "1" ]]; then
  bash tools/local/run_agent_readyz_report.sh \
    --output "$AGENT_READYZ_PATH" \
    --base-url "$AGENT_READYZ_BASE_URL" \
    --timeout-s "$AGENT_READYZ_TIMEOUT_S"
fi
if [[ "$WITH_DECISION_TRACE_SCHEMA_GUARD" == "1" ]]; then
  bash tools/local/run_agent_decision_trace_schema_report.sh \
    --output "$DECISION_TRACE_SCHEMA_GUARD_PATH"
fi

ARGS=(--glob "$GLOB" --output "$OUT")
if [[ "$COMPACT" == "1" ]]; then
  ARGS+=(--compact)
fi
if ((${#EXTRA_ARGS[@]} > 0)); then
  ARGS+=("${EXTRA_ARGS[@]}")
fi

python3 -m verification.reports.aggregate_reports "${ARGS[@]}"
echo "[ok] aggregate report generated: $OUT"
