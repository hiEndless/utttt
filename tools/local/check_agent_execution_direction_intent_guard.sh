#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_agent_execution_direction_intent_guard.sh [report_json] [max_none] [max_invalid] [min_total]

Description:
  校验 agent->execution 请求体 direction_intent 是否出现非规范 none 或非法值。

Args:
  report_json  报告路径（默认 verification/reports/agent_execution_direction_intent.latest.json）
  max_none     允许的 none 最大数量（默认 0）
  max_invalid  允许的 invalid 最大数量（默认 0）
  min_total    最小样本量（默认 1，低于阈值仅提示并通过）

Failure Codes:
  exit 1  none/invalid 超阈值
  exit 2  输入文件缺失或不可读
  exit 3  报告解析失败
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

REPORT_PATH="${1:-verification/reports/agent_execution_direction_intent.latest.json}"
MAX_NONE_RAW="${2:-0}"
MAX_INVALID_RAW="${3:-0}"
MIN_TOTAL_RAW="${4:-1}"

if ! test -r "$REPORT_PATH"; then
  echo "[failed] agent execution direction_intent report not readable: $REPORT_PATH"
  exit 2
fi

"$PY_BIN" - <<'PY' "$REPORT_PATH" "$MAX_NONE_RAW" "$MAX_INVALID_RAW" "$MIN_TOTAL_RAW"
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
try:
    max_none = int(str(sys.argv[2] or "0").strip())
    max_invalid = int(str(sys.argv[3] or "0").strip())
    min_total = int(str(sys.argv[4] or "1").strip())
except Exception:
    print("[failed] invalid threshold args")
    raise SystemExit(3)

try:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] invalid report json: {report_path} err={exc}")
    raise SystemExit(3)

if not isinstance(payload, dict):
    print(f"[failed] invalid report payload type: {report_path}")
    raise SystemExit(3)

schema_version = str(payload.get("schema_version") or "").strip()
if schema_version and schema_version != "agent-execution-direction-intent-report-v1":
    print(f"[failed] unsupported schema_version: {schema_version}")
    raise SystemExit(3)

summary = payload.get("summary")
if not isinstance(summary, dict):
    print("[failed] report.summary missing")
    raise SystemExit(3)

total = int(summary.get("direction_intent_total") or 0)
noncanonical_none_count = int(summary.get("noncanonical_none_count") or 0)
invalid_count = int(summary.get("invalid_count") or 0)

if total < max(0, min_total):
    print("[skip] agent execution direction_intent guard: insufficient samples")
    print(
        f"[info] report={report_path} total={total} min_total={min_total} "
        f"noncanonical_none={noncanonical_none_count} invalid={invalid_count}"
    )
    raise SystemExit(0)

if noncanonical_none_count > max_none or invalid_count > max_invalid:
    print("[failed] agent execution direction_intent guard")
    print(
        f"[info] report={report_path} total={total} noncanonical_none={noncanonical_none_count} max_none={max_none} "
        f"invalid={invalid_count} max_invalid={max_invalid}"
    )
    for item in list(payload.get("noncanonical_none_samples") or [])[:10]:
        if isinstance(item, dict):
            print(
                f"- noncanonical_none_sample line_no={int(item.get('line_no') or 0)} "
                f"event_id={str(item.get('event_id') or '')} direction_intent={str(item.get('direction_intent') or '')}"
            )
    for item in list(payload.get("invalid_samples") or [])[:10]:
        if isinstance(item, dict):
            print(
                f"- invalid_sample line_no={int(item.get('line_no') or 0)} "
                f"event_id={str(item.get('event_id') or '')} direction_intent={str(item.get('direction_intent') or '')}"
            )
    raise SystemExit(1)

print("[passed] agent execution direction_intent guard")
print(
    f"[info] report={report_path} total={total} noncanonical_none={noncanonical_none_count} max_none={max_none} "
    f"invalid={invalid_count} max_invalid={max_invalid}"
)
PY
