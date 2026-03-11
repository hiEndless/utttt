#!/usr/bin/env bash
set -euo pipefail

python3 -m verification.diff.json_diff "$@"
