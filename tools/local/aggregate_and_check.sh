#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
MEMORY_SUMMARY_PATH="verification/reports/memory_summary.latest.json"
WITH_MEMORY_SUMMARY=0
SKIP_THRESHOLDS=0
COMPACT=0
MAX_LEGACY_CONFIDENCE_RATIO="-1"

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/aggregate_and_check.sh [options]

Options:
  --with-memory-summary         先生成 memory summary 再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --compact                     生成紧凑 JSON（透传给 aggregate_reports --compact）
  --skip-thresholds             仅聚合，不执行阈值检查
  --max-legacy-confidence-ratio <float>
                               execution legacy confidence 占比上限（默认 -1 忽略）
  --help, -h                    显示帮助
USAGE
      exit 0
      ;;
    --with-memory-summary)
      WITH_MEMORY_SUMMARY=1
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
if [[ "$COMPACT" == "1" ]]; then
  AGGREGATE_ARGS+=(--compact)
fi
bash tools/local/verify_report_aggregate.sh "${AGGREGATE_ARGS[@]}"
if [[ "$SKIP_THRESHOLDS" == "0" ]]; then
  python3 -m verification.reports.check_thresholds \
    --summary "$SUMMARY_PATH" \
    --min-pass-rate 1.0 \
    --max-failed 0 \
    --min-reports 1 \
    --max-semantic-errors 0 \
    --max-legacy-confidence-ratio "$MAX_LEGACY_CONFIDENCE_RATIO"
fi
