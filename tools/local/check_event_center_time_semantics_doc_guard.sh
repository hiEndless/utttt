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

ROOT = Path.cwd()
README = ROOT / "services" / "event_center_new" / "README.md"
GLOSSARY = ROOT / "docs" / "contracts" / "SEMANTIC_GLOSSARY.md"

errors: list[str] = []

readme_text = README.read_text(encoding="utf-8")
glossary_text = GLOSSARY.read_text(encoding="utf-8")

if "docs/contracts/SEMANTIC_GLOSSARY.md" not in readme_text:
    errors.append("event_center_new README must reference docs/contracts/SEMANTIC_GLOSSARY.md")
for field in ("event_ts_ms", "processed_ts_ms"):
    if field not in readme_text:
        errors.append(f"event_center_new README missing field: {field}")

if "services/event_center_new/README.md" not in glossary_text:
    errors.append("SEMANTIC_GLOSSARY must reference services/event_center_new/README.md")
for field in ("event_ts_ms", "processed_ts_ms"):
    if field not in glossary_text:
        errors.append(f"SEMANTIC_GLOSSARY missing field: {field}")

if errors:
    print("[failed] event_center time semantics doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] event_center time semantics doc guard")
print("[info] checked mutual references and selected_event time fields")
PY

