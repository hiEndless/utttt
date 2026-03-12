#!/usr/bin/env bash
set -euo pipefail

GLOB='verification/reports/*.json'
OUT='verification/reports/summary.latest.json'
MEMORY_SUMMARY_PATH='verification/reports/memory_summary.latest.json'
COMPACT=0
WITH_MEMORY_SUMMARY=0
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
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  bash tools/local/run_agent_memory_summary_report.sh "$MEMORY_SUMMARY_PATH"
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
