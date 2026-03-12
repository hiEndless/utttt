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
from typing import Any

import yaml

ROOT = Path.cwd()
POLICY_PATH = ROOT / "contracts/semantic_policies/source_semantics.yaml"
EVENT_CENTER_BUILDER = ROOT / "services/event_center_new/ec/context/builder.py"
MARKET_STATE_SERVICE = ROOT / "services/market_state_engine/src/service.py"
AGENT_CONTEXT_BUILDER = ROOT / "services/agent_server_new/app/context_builder.py"

errors: list[str] = []

if not POLICY_PATH.is_file():
    errors.append(f"missing policy file: {POLICY_PATH.relative_to(ROOT)}")
    policy: dict[str, Any] = {}
else:
    policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8")) or {}

if not isinstance(policy.get("version"), int):
    errors.append("source_semantics.version must be integer")

policies = policy.get("policies")
if not isinstance(policies, list) or not policies:
    errors.append("source_semantics.policies must be non-empty list")
    policies = []

target = None
for item in policies:
    if isinstance(item, dict) and str(item.get("name") or "").strip() == "alternative_sources_summary":
        target = item
        break
if not isinstance(target, dict):
    errors.append("missing policy: alternative_sources_summary")
    target = {}

required_keys = target.get("required_keys") or []
if not isinstance(required_keys, list):
    errors.append("alternative_sources_summary.required_keys must be list")
    required_keys = []
required_set = {str(x).strip() for x in required_keys if str(x).strip()}
expected = {
    "available_sources",
    "unavailable_sources",
    "provider_states",
    "data_sources",
    "inference_sources",
    "feature_keys",
    "evidence_counts",
}
if not expected.issubset(required_set):
    errors.append(
        "alternative_sources_summary.required_keys missing: "
        + str(sorted(expected - required_set))
    )

for path in (EVENT_CENTER_BUILDER, MARKET_STATE_SERVICE, AGENT_CONTEXT_BUILDER):
    if not path.is_file():
        errors.append(f"missing implementation file: {path.relative_to(ROOT)}")

event_text = EVENT_CENTER_BUILDER.read_text(encoding="utf-8")
for token in ('"data_sources"', '"inference_sources"', 'event_center_new.selector', 'event_center_new.{name}'):
    if token not in event_text:
        errors.append(f"event_center builder missing token: {token}")

state_text = MARKET_STATE_SERVICE.read_text(encoding="utf-8")
for token in ('"data_source"', '"inference_source"', 'feature_service.{src}', 'event_center_new.{src}'):
    if token not in state_text:
        errors.append(f"market_state service missing token: {token}")

agent_text = AGENT_CONTEXT_BUILDER.read_text(encoding="utf-8")
for token in ('"data_sources"', '"inference_sources"', 'state.startswith("event_")', 'feature_service.{name}', 'event_center_new.{name}'):
    if token not in agent_text:
        errors.append(f"agent context builder missing token: {token}")

if errors:
    print("[failed] source semantics guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] source semantics guard")
print(f"[info] policy={POLICY_PATH.relative_to(ROOT)}")
PY
