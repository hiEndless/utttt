#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/print_agent_signal_decision_replay_recommendation_hint.sh [recommendation_json]

Description:
  读取 recommendation artifact，输出发布候选提示（非阻断）：
  - [release-candidate] 当 status=recommend
  - [release-hold] 当 status=hold|skip|failed 或文件缺失
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
if not path.is_file():
    print(f"[release-hold] recommendation missing path={path}")
    raise SystemExit(0)

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[release-hold] recommendation invalid_json path={path} error={exc}")
    raise SystemExit(0)

if str(payload.get("schema_version") or "") != "agent-signal-decision-replay-trend-recommendation-v1":
    print(
        f"[release-hold] recommendation unsupported_schema_version "
        f"path={path} schema_version={payload.get('schema_version')}"
    )
    raise SystemExit(0)

status = str(payload.get("status") or "").strip().lower()
action = str(payload.get("recommend_action") or "none").strip()
source = str(payload.get("source_type") or "social_news").strip().lower()
ratio = float(payload.get("ratio") or 0.0)
latest_ratio = float(payload.get("latest_ratio") or 0.0)
consecutive = int(payload.get("consecutive_days") or 0)

if status == "recommend":
    print(
        f"[release-candidate] source={source} action={action} "
        f"ratio={ratio:.6f} latest_ratio={latest_ratio:.6f} consecutive_days={consecutive}"
    )
else:
    reason = str(payload.get("reason") or "not_recommended")
    print(
        f"[release-hold] source={source} status={status or 'unknown'} reason={reason} "
        f"ratio={ratio:.6f} latest_ratio={latest_ratio:.6f} consecutive_days={consecutive}"
    )
raise SystemExit(0)
PY
