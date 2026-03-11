#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"

python3 -m verification.reports.aggregate_reports --glob 'verification/reports/*.json' --output "$SUMMARY_PATH"
python3 -m verification.reports.check_thresholds --summary "$SUMMARY_PATH" --min-pass-rate 1.0 --max-failed 0 --min-reports 1
