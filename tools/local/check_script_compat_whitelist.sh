#!/usr/bin/env bash
set -euo pipefail

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - <<'PY'
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import yaml

cfg = Path("verification/guards/script_compat_whitelist.yaml")
if not cfg.exists():
    raise SystemExit("[failed] missing verification/guards/script_compat_whitelist.yaml")

data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}

missing: list[str] = []
untracked: list[str] = []
invalid_wrapper: list[str] = []

categories = [
    "hard_pinned_by_workflows",
    "hard_pinned_by_snapshot_or_help_guards",
    "hard_pinned_by_text_wiring_guards",
]

seen: set[str] = set()
for cat in categories:
    for item in data.get(cat, []) or []:
        path = str((item or {}).get("path", "")).strip()
        if not path:
            continue
        seen.add(path)

for path in sorted(seen):
    p = Path(path)
    if not p.exists():
        missing.append(path)
        continue
    r = subprocess.run(["git", "ls-files", "--error-unmatch", path], capture_output=True, text=True)
    if r.returncode != 0:
        untracked.append(path)

for item in data.get("compatibility_wrappers_retained", []) or []:
    path = str((item or {}).get("path", "")).strip()
    target = str((item or {}).get("target", "")).strip()
    if not path or not target:
        continue
    p = Path(path)
    if not p.exists():
        missing.append(path)
        continue
    text = p.read_text(encoding="utf-8")
    if target not in text:
        invalid_wrapper.append(f"{path} missing target reference: {target}")

if missing or untracked or invalid_wrapper:
    print("[failed] script compat whitelist check failed")
    for x in missing:
        print(f"- missing: {x}")
    for x in untracked:
        print(f"- untracked: {x}")
    for x in invalid_wrapper:
        print(f"- invalid_wrapper: {x}")
    raise SystemExit(1)

print("[passed] script compat whitelist check passed")
PY
