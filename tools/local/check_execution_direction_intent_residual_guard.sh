#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_execution_direction_intent_residual_guard.sh [report_json] [max_none] [min_total]

Description:
  校验 execution direction_intent 残留报告中的 none_count 是否超过阈值。

Args:
  report_json  报告路径（默认 verification/reports/execution_direction_intent_residual.latest.json）
  max_none     允许的 none 最大数量（默认 0）
  min_total    最小样本量（默认 1；样本不足时仅提示并通过）

Failure Codes:
  exit 1  none_count 超过阈值
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

REPORT_PATH="${1:-verification/reports/execution_direction_intent_residual.latest.json}"
MAX_NONE_RAW="${2:-0}"
MIN_TOTAL_RAW="${3:-1}"

if ! test -r "$REPORT_PATH"; then
  echo "[failed] execution direction_intent report not readable: $REPORT_PATH"
  exit 2
fi

"$PY_BIN" - <<'PY' "$REPORT_PATH" "$MAX_NONE_RAW" "$MIN_TOTAL_RAW"
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
max_none_raw = str(sys.argv[2] or "0").strip()
min_total_raw = str(sys.argv[3] or "1").strip()

try:
    max_none = int(max_none_raw)
    min_total = int(min_total_raw)
except Exception:
    print(f"[failed] invalid threshold args: max_none={max_none_raw} min_total={min_total_raw}")
    raise SystemExit(3)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] invalid report json: {report_path} err={exc}")
    raise SystemExit(3)

if not isinstance(report, dict):
    print(f"[failed] invalid report payload type: {report_path}")
    raise SystemExit(3)

schema_version = str(report.get("schema_version") or "").strip()
if schema_version and schema_version != "execution-direction-intent-residual-report-v1":
    print(f"[failed] unsupported schema_version: {schema_version}")
    raise SystemExit(3)

summary = report.get("summary")
if not isinstance(summary, dict):
    print("[failed] report.summary missing")
    raise SystemExit(3)

total = int(summary.get("direction_intent_total") or 0)
none_count = int(summary.get("none_count") or 0)

if total < max(0, min_total):
    print("[skip] execution direction_intent residual guard: insufficient samples")
    print(f"[info] report={report_path} total={total} min_total={min_total} none_count={none_count} max_none={max_none}")
    raise SystemExit(0)

if none_count > max_none:
    print("[failed] execution direction_intent residual guard")
    print(f"[info] report={report_path} total={total} none_count={none_count} max_none={max_none}")
    for item in list(report.get("none_examples") or [])[:10]:
        if not isinstance(item, dict):
            continue
        print(
            f"- line_no={int(item.get('line_no') or 0)} "
            f"event_id={str(item.get('event_id') or '')} "
            f"path={str(item.get('path') or '')} value={str(item.get('value') or '')}"
        )
    raise SystemExit(1)

print("[passed] execution direction_intent residual guard")
print(f"[info] report={report_path} total={total} none_count={none_count} max_none={max_none}")
PY
