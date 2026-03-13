#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH="${1:-verification/reports/agent_decision_agent_key.latest.json}"
MAX_UNKNOWN_COUNT="${2:--1}"
MAX_GENERIC_RATIO="${3:--1}"

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - "$REPORT_PATH" "$MAX_UNKNOWN_COUNT" "$MAX_GENERIC_RATIO" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: <report_path> <max_unknown_count> <max_generic_ratio>")

report_path = Path(sys.argv[1])
try:
    max_unknown_count = int(sys.argv[2])
except Exception:
    max_unknown_count = -1
try:
    max_generic_ratio = float(sys.argv[3])
except Exception:
    max_generic_ratio = -1.0

if max_unknown_count < 0 and max_generic_ratio < 0:
    print(
        f"[skip] decision_agent_key guard disabled "
        f"(max_unknown_count={max_unknown_count} max_generic_ratio={max_generic_ratio})"
    )
    raise SystemExit(0)

if not report_path.is_file():
    print(f"[failed] decision_agent_key guard missing report: {report_path}")
    raise SystemExit(1)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] decision_agent_key guard invalid json: {exc}")
    raise SystemExit(1)

summary = dict(report.get("summary") or {})
unknown_count = int(summary.get("unknown_count") or 0)
decision_trace_record_count = int(summary.get("decision_trace_record_count") or 0)
generic_count = int(summary.get("generic_count") or 0)
try:
    generic_ratio = float(summary.get("generic_ratio"))
except Exception:
    denom = max(1, decision_trace_record_count)
    generic_ratio = float(generic_count) / float(denom)
top_unknown = list(report.get("top_unknown_agent_keys") or [])

if max_unknown_count >= 0 and unknown_count > max_unknown_count:
    print(
        f"[failed] decision_agent_key guard unknown_count={unknown_count} "
        f"> max_unknown_count={max_unknown_count}"
    )
    for item in top_unknown[:10]:
        if not isinstance(item, dict):
            continue
        key = str(item.get("decision_agent_key") or "")
        count = int(item.get("count") or 0)
        print(f"[failed] top_unknown decision_agent_key={key} count={count}")
    raise SystemExit(1)

if max_generic_ratio >= 0 and generic_ratio > max_generic_ratio:
    print(
        f"[failed] decision_agent_key guard generic_ratio={generic_ratio:.6f} "
        f"> max_generic_ratio={max_generic_ratio:.6f} "
        f"(generic_count={generic_count} decision_trace_record_count={decision_trace_record_count})"
    )
    raise SystemExit(1)

print(
    f"[passed] decision_agent_key guard unknown_count={unknown_count} "
    f"max_unknown_count={max_unknown_count} "
    f"generic_ratio={generic_ratio:.6f} max_generic_ratio={max_generic_ratio:.6f}"
)
raise SystemExit(0)
PY
