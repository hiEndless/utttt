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
import sys

import yaml

MAP_PATH = Path("services/services_map.yaml")
if not MAP_PATH.exists():
    raise SystemExit("[failed] missing services/services_map.yaml")

data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8")) or {}
services = data.get("services") or []

errors: list[str] = []

for item in services:
    if not isinstance(item, dict):
        continue
    name = str(item.get("name") or "unknown")
    status = str(item.get("status") or "")

    target = str(item.get("target_path") or "")
    if target and not Path(target).exists():
        errors.append(f"{name}: missing target_path {target}")

    readme = str(item.get("scaffold_readme") or "")
    if readme and not Path(readme).exists():
        errors.append(f"{name}: missing scaffold_readme {readme}")

    for p in item.get("soft_entrypoints") or []:
        p = str(p)
        if p and not Path(p).exists():
            errors.append(f"{name}: missing soft_entrypoint {p}")

    if status == "pilot_entrypoint_migrated":
        migrated = item.get("pilot_migrated_impl") or []
        wrappers = item.get("legacy_wrapper") or []
        if not migrated:
            errors.append(f"{name}: status=pilot_entrypoint_migrated but no pilot_migrated_impl")
        if not wrappers:
            errors.append(f"{name}: status=pilot_entrypoint_migrated but no legacy_wrapper")
        for p in migrated:
            p = str(p)
            if p and not Path(p).exists():
                errors.append(f"{name}: missing pilot_migrated_impl {p}")
        for p in wrappers:
            p = str(p)
            if p and not Path(p).exists():
                errors.append(f"{name}: missing legacy_wrapper {p}")

if errors:
    print("[failed] services map consistency check failed")
    for e in errors:
        print(f"- {e}")
    raise SystemExit(1)

print("[passed] services map consistency check passed")
PY
