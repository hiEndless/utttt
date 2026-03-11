#!/usr/bin/env bash
set -euo pipefail

python3 -m verification.reports.check_thresholds "$@"
