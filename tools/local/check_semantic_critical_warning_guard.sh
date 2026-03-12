#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_semantic_critical_warning_guard.sh [audit_report_json] [budget_yaml]

Description:
  读取 semantic audit 报告中的 warnings，按 budget 中 critical_fields 做阻断检查。

Args:
  audit_report_json  semantic audit 报告路径（默认 verification/reports/semantic_audit.latest.json）
  budget_yaml        关键字段预算文件（默认 verification/reports/semantic_critical_fields.yaml）

Failure Codes:
  exit 1  命中 critical field warning（阻断）
  exit 2  输入文件缺失或不可读
  exit 3  报告/预算解析失败
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

AUDIT_REPORT="${1:-verification/reports/semantic_audit.latest.json}"
BUDGET_FILE="${2:-verification/reports/semantic_critical_fields.yaml}"

if ! test -r "$AUDIT_REPORT"; then
  echo "[failed] audit report not readable: $AUDIT_REPORT"
  exit 2
fi
if ! test -r "$BUDGET_FILE"; then
  echo "[failed] budget file not readable: $BUDGET_FILE"
  exit 2
fi

"$PY_BIN" - <<'PY' "$AUDIT_REPORT" "$BUDGET_FILE"
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

audit_path = Path(sys.argv[1])
budget_path = Path(sys.argv[2])

try:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] invalid audit report json: {audit_path} err={exc}")
    raise SystemExit(3)
try:
    budget = yaml.safe_load(budget_path.read_text(encoding="utf-8")) or {}
except Exception as exc:
    print(f"[failed] invalid budget yaml: {budget_path} err={exc}")
    raise SystemExit(3)

critical = {str(x).strip() for x in (budget.get("critical_fields") or []) if str(x).strip()}
warnings = [str(x) for x in (audit.get("warnings") or [])]

hit: list[str] = []
pat = re.compile(r"^field\s+([A-Za-z0-9_]+):")
for w in warnings:
    m = pat.match(w)
    if not m:
        continue
    field = m.group(1)
    if field in critical:
        hit.append(w)

if hit:
    print("[failed] semantic critical warning guard")
    print(f"[info] report={audit_path} budget={budget_path}")
    for item in hit:
        print(f"- {item}")
    raise SystemExit(1)

print("[passed] semantic critical warning guard")
print(f"[info] report={audit_path} budget={budget_path} critical_fields={len(critical)} warnings={len(warnings)}")
PY
