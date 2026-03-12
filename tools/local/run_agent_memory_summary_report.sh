#!/usr/bin/env bash
set -euo pipefail

OUT_PATH="${1:-verification/reports/memory_summary.latest.json}"

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

exec "$PY_BIN" -m services.agent_server_new.memory_summary_runner --output "$OUT_PATH" "${@:2}"
