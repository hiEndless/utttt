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
MSE_PIPELINE = ROOT / "docs" / "contracts" / "pipelines" / "market_state_engine_data_pipeline.md"
AGENT_PIPELINE = ROOT / "docs" / "contracts" / "pipelines" / "agent_server_new_data_pipeline.md"
EXEC_PIPELINE = ROOT / "docs" / "contracts" / "pipelines" / "execution_service_data_pipeline.md"
EXEC_API = ROOT / "services" / "execution_service" / "docs" / "api.md"

errors: list[str] = []

readme_text = README.read_text(encoding="utf-8")
glossary_text = GLOSSARY.read_text(encoding="utf-8")
mse_pipeline_text = MSE_PIPELINE.read_text(encoding="utf-8")
agent_pipeline_text = AGENT_PIPELINE.read_text(encoding="utf-8")
exec_pipeline_text = EXEC_PIPELINE.read_text(encoding="utf-8")
exec_api_text = EXEC_API.read_text(encoding="utf-8")

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

for name, text in (
    ("market_state_engine pipeline doc", mse_pipeline_text),
    ("agent_server_new pipeline doc", agent_pipeline_text),
):
    if "docs/contracts/SEMANTIC_GLOSSARY.md" not in text:
        errors.append(f"{name} must reference docs/contracts/SEMANTIC_GLOSSARY.md")
    for field in ("event_ts_ms", "processed_ts_ms"):
        if field not in text:
            errors.append(f"{name} missing field: {field}")

for name, text in (
    ("execution_service pipeline doc", exec_pipeline_text),
    ("execution_service api doc", exec_api_text),
):
    if "docs/contracts/SEMANTIC_GLOSSARY.md" not in text:
        errors.append(f"{name} must reference docs/contracts/SEMANTIC_GLOSSARY.md")
    if "event_ts_ms" not in text or "processed_ts_ms" not in text:
        errors.append(f"{name} must declare event_ts_ms/processed_ts_ms semantic boundary")
    if "ts_ms" not in text:
        errors.append(f"{name} missing ts_ms compatibility mention")

if errors:
    print("[failed] cross-service time semantics doc guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] cross-service time semantics doc guard")
print("[info] checked time semantics references across event/state/agent/execution docs")
PY
