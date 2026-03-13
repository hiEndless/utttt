#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/print_signal_decision_llm_observe_trend_recommendation_hint.sh [recommendation_json]

Description:
  读取 LLM observe trend recommendation artifact，输出发布候选提示（非阻断）：
  - [release-candidate] 当 status=recommend
  - [release-hold] 当 status=hold|skip 或文件缺失
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

RECOMMENDATION_PATH="${1:-verification/reports/agent_signal_decision_llm_observe_agent_key_trend_recommendation.latest.json}"

"$PY_BIN" - <<'PY' "$RECOMMENDATION_PATH"
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print(f"[release-hold] llm_observe_recommendation missing path={path}")
    raise SystemExit(0)

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[release-hold] llm_observe_recommendation invalid_json path={path} error={exc}")
    raise SystemExit(0)

if str(payload.get("schema_version") or "") != "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1":
    print(
        f"[release-hold] llm_observe_recommendation unsupported_schema_version "
        f"path={path} schema_version={payload.get('schema_version')}"
    )
    raise SystemExit(0)

status = str(payload.get("status") or "").strip().lower()
action = str(payload.get("recommend_action") or "none").strip()
reason = str(payload.get("reason") or "unknown").strip()
warn_agent_keys = [str(x).strip().lower() for x in list(payload.get("warn_agent_keys") or []) if str(x).strip()]
warn_joined = ",".join(sorted(warn_agent_keys)) if warn_agent_keys else "none"
reports = int(payload.get("reports") or 0)
days = int(payload.get("window_days") or 0)
min_ratio = float(payload.get("min_ratio") or 0.0)
min_consecutive = int(payload.get("min_consecutive_days") or 0)

if status == "recommend":
    print(
        f"[release-candidate] llm_observe status={status} action={action} "
        f"warn_agent_keys={warn_joined} reports={reports} window_days={days} "
        f"min_ratio={min_ratio:.6f} min_consecutive_days={min_consecutive}"
    )
else:
    print(
        f"[release-hold] llm_observe status={status or 'unknown'} reason={reason} action={action} "
        f"warn_agent_keys={warn_joined} reports={reports} window_days={days} "
        f"min_ratio={min_ratio:.6f} min_consecutive_days={min_consecutive}"
    )
raise SystemExit(0)
PY
