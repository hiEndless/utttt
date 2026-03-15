#!/usr/bin/env bash
set -euo pipefail

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - <<'PY'
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
targets = [
    ROOT / "docs" / "CONTRACT_INDEX.md",
    ROOT / "docs" / "contracts" / "pipelines" / "agent_server_new_data_pipeline.md",
    ROOT / "docs" / "contracts" / "TERMINOLOGY_WHITELIST.md",
]

errors: list[str] = []
for p in targets:
    if not p.is_file():
        errors.append(f"missing doc: {p.as_posix()}")

if errors:
    print("[failed] direction enum doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

index_text = targets[0].read_text(encoding="utf-8")
agent_pipeline_text = targets[1].read_text(encoding="utf-8")
whitelist_text = targets[2].read_text(encoding="utf-8")

if "agent_signal_direction_canonical: neutral" not in index_text:
    errors.append("CONTRACT_INDEX missing agent_signal_direction_canonical: neutral")
if "仅允许 `long|short|neutral`" not in index_text:
    errors.append("CONTRACT_INDEX missing strict direction enum note")

if re.search(r"long/short/none", agent_pipeline_text):
    errors.append("agent pipeline doc still contains long/short/none")
if re.search(r'Direction = "long" \| "short" \| "none"', agent_pipeline_text):
    errors.append("agent pipeline doc still defines Direction with none")
if "long/short/neutral" not in agent_pipeline_text:
    errors.append("agent pipeline doc missing long/short/neutral enum anchor")

if "canonical：`long | short | neutral`" not in whitelist_text:
    errors.append("TERMINOLOGY_WHITELIST missing canonical direction enum")

if errors:
    print("[failed] direction enum doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] direction enum doc guard")
print("[info] checked direction enum wording across CONTRACT_INDEX / agent pipeline / terminology whitelist")
PY
