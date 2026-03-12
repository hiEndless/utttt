#!/usr/bin/env bash
set -euo pipefail

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

AUDIT_REPORT="${1:-verification/reports/semantic_audit.latest.json}"
BUDGET_FILE="${2:-verification/reports/semantic_critical_fields.yaml}"

"$PY_BIN" - <<'PY' "$AUDIT_REPORT" "$BUDGET_FILE"
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

audit_path = Path(sys.argv[1])
budget_path = Path(sys.argv[2])

audit = json.loads(audit_path.read_text(encoding="utf-8"))
budget = yaml.safe_load(budget_path.read_text(encoding="utf-8")) or {}

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
