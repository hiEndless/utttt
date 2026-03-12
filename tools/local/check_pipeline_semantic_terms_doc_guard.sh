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
PIPELINES = ROOT / "docs" / "contracts" / "pipelines"
EVENT_DOC = PIPELINES / "event_center_new_data_contracts.md"
AGENT_DOC = PIPELINES / "agent_server_new_data_pipeline.md"
STATE_DOC = PIPELINES / "market_state_engine_data_pipeline.md"
EXEC_DOC = PIPELINES / "execution_service_data_pipeline.md"

errors: list[str] = []

for p in (EVENT_DOC, AGENT_DOC, STATE_DOC, EXEC_DOC):
    if not p.is_file():
        errors.append(f"missing pipeline doc: {p.as_posix()}")

if errors:
    print("[failed] pipeline semantic terms doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

event_text = EVENT_DOC.read_text(encoding="utf-8")
agent_text = AGENT_DOC.read_text(encoding="utf-8")
state_text = STATE_DOC.read_text(encoding="utf-8")
exec_text = EXEC_DOC.read_text(encoding="utf-8")

if "docs/contracts/SEMANTIC_GLOSSARY.md" not in event_text:
    errors.append("event_center pipeline doc missing SEMANTIC_GLOSSARY reference")
for token in ("source_market_state", "action_risk_bias", "evidence_confidence"):
    if token not in event_text:
        errors.append(f"event_center pipeline doc missing semantic anchor: {token}")

for token in ("decision_confidence", "deprecated alias"):
    if token not in agent_text:
        errors.append(f"agent pipeline doc missing semantic anchor: {token}")

if "state_features.semantic_contract" not in state_text:
    errors.append("market_state pipeline doc missing semantic anchor: state_features.semantic_contract")

for token in ("decision_confidence", "deprecated", "confidence"):
    if token not in exec_text:
        errors.append(f"execution pipeline doc missing semantic anchor: {token}")

if errors:
    print("[failed] pipeline semantic terms doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] pipeline semantic terms doc guard")
print("[info] checked confidence/risk_bias/market_state semantic anchors across pipeline docs")
PY
