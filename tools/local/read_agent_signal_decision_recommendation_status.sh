#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/read_agent_signal_decision_recommendation_status.sh [recommendation_json]

Description:
  读取 recommendation artifact 并输出归一化状态枚举（单行）：
  - recommend | hold | skip
  - missing | invalid_json | unsupported_schema_version | unknown_status
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

RECOMMENDATION_PATH="${1:-verification/reports/agent_signal_decision_replay_recommendation.latest.json}"

"$PY_BIN" - <<'PY' "$RECOMMENDATION_PATH"
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not str(path).strip():
    print("missing")
    raise SystemExit(0)
if not path.exists():
    print("missing")
    raise SystemExit(0)

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("invalid_json")
    raise SystemExit(0)

if str(payload.get("schema_version") or "") != "agent-signal-decision-replay-trend-recommendation-v1":
    print("unsupported_schema_version")
    raise SystemExit(0)

status = str(payload.get("status") or "").strip().lower()
if status in {"recommend", "hold", "skip"}:
    print(status)
else:
    print("unknown_status")
PY
