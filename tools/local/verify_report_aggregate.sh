#!/usr/bin/env bash
set -euo pipefail

python3 -m verification.reports.aggregate_reports "$@"
