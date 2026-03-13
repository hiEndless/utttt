#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_agent_action_hint_cases_guard.sh [cases_report_json] [max_cases]

Description:
  读取 action_hint mismatch 回放 artifact，按 count 做阻断检查，并打印前 N 条 event_id 便于排障。

Args:
  cases_report_json  回放报告路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  max_cases          允许的最大 mismatch 数（默认 0）

Failure Codes:
  exit 1  mismatch 数超过阈值（阻断）
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

CASES_REPORT="${1:-verification/reports/agent_action_hint_cases.latest.json}"
MAX_CASES_RAW="${2:-0}"

if ! test -r "$CASES_REPORT"; then
  echo "[failed] action_hint cases report not readable: $CASES_REPORT"
  exit 2
fi

"$PY_BIN" - <<'PY' "$CASES_REPORT" "$MAX_CASES_RAW"
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
max_cases_raw = str(sys.argv[2] or "0").strip()

try:
    max_cases = int(max_cases_raw)
except Exception:
    print(f"[failed] invalid max_cases: {max_cases_raw}")
    raise SystemExit(3)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] invalid action_hint cases report json: {report_path} err={exc}")
    raise SystemExit(3)

if not isinstance(report, dict):
    print(f"[failed] invalid action_hint cases report payload type: {report_path}")
    raise SystemExit(3)

schema_version = str(report.get("schema_version") or "").strip()
if schema_version and schema_version != "agent-action-hint-cases-v1":
    print(f"[failed] unsupported action_hint cases schema_version: {schema_version}")
    raise SystemExit(3)

rows = [dict(x) for x in list(report.get("rows") or []) if isinstance(x, dict)]
try:
    count = int(report.get("count") or len(rows))
except Exception:
    count = len(rows)

if count > max_cases:
    print("[failed] action_hint cases guard")
    print(f"[info] report={report_path} count={count} max_cases={max_cases}")
    for item in rows[:10]:
        event_id = str(item.get("event_id") or "")
        status = str(item.get("status") or "")
        expected = str(item.get("expected_hint") or "")
        actual = str(item.get("actual_hint") or "")
        print(f"- event_id={event_id} status={status} expected_hint={expected} actual_hint={actual}")
    raise SystemExit(1)

print("[passed] action_hint cases guard")
print(f"[info] report={report_path} count={count} max_cases={max_cases}")
PY
