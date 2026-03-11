#!/usr/bin/env bash
set -euo pipefail

OUT="verification/reports/quick.latest.json"
bash verification/run_suite.sh --suite=quick --report-json="$OUT"
echo "[ok] report generated: $OUT"
