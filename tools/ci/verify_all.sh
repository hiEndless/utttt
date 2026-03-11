#!/usr/bin/env bash
set -euo pipefail

MODE="new_arch_full"
REPORT_JSON=""

for arg in "$@"; do
  case "$arg" in
    --quick)
      MODE="quick"
      ;;
    --event-center-quick)
      MODE="new_arch_event_center_quick"
      ;;
    --report-json=*)
      REPORT_JSON="${arg#*=}"
      ;;
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/ci/verify_all.sh
  bash tools/ci/verify_all.sh --quick
  bash tools/ci/verify_all.sh --event-center-quick
  bash tools/ci/verify_all.sh --quick --report-json=verification/reports/quick.latest.json

Routing:
  full                -> verification/run_suite.sh --suite=new_arch_full
  quick               -> verification/run_suite.sh --suite=quick
  event-center-quick  -> verification/run_suite.sh --suite=new_arch_event_center_quick
USAGE
      exit 0
      ;;
    *)
      echo "[fail] unsupported arg: $arg"
      exit 1
      ;;
  esac
done

if [[ -n "$REPORT_JSON" ]]; then
  bash verification/run_suite.sh --suite="$MODE" --report-json="$REPORT_JSON"
  exit $?
fi

bash verification/run_suite.sh --suite="$MODE"
