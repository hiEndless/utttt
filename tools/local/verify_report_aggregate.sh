#!/usr/bin/env bash
set -euo pipefail

GLOB='verification/reports/*.json'
OUT='verification/reports/summary.latest.json'
COMPACT=0
EXTRA_ARGS=()

while (($# > 0)); do
  case "$1" in
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
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

ARGS=(--glob "$GLOB" --output "$OUT")
if [[ "$COMPACT" == "1" ]]; then
  ARGS+=(--compact)
fi
if ((${#EXTRA_ARGS[@]} > 0)); then
  ARGS+=("${EXTRA_ARGS[@]}")
fi

python3 -m verification.reports.aggregate_reports "${ARGS[@]}"
echo "[ok] aggregate report generated: $OUT"
