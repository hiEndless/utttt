#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
MEMORY_SUMMARY_PATH="verification/reports/memory_summary.latest.json"
WITH_MEMORY_SUMMARY=0
SKIP_THRESHOLDS=0
COMPACT=0

while (($# > 0)); do
  case "$1" in
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
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  bash tools/local/run_agent_memory_summary_report.sh "$MEMORY_SUMMARY_PATH"
fi

AGGREGATE_ARGS=(--glob 'verification/reports/*.json' --output "$SUMMARY_PATH")
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
    --max-semantic-errors 0
fi
