#!/usr/bin/env bash
set -euo pipefail

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - <<'PY'
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path.cwd()
POLICY_PATH = ROOT / "contracts/semantic_policies/field_semantics.yaml"
SOURCE_POLICY_PATH = ROOT / "contracts/semantic_policies/source_semantics.yaml"

ALLOWED_OWNERS = {
    "feature_service",
    "market_state_engine",
    "event_center_new",
    "agent_server_new",
    "execution_service",
    "cross_service",
}
ALLOWED_LIFECYCLE = {"active", "deprecated", "reserved"}
REQUIRED_FIELDS = {
    "decision_confidence",
    "confidence",
    "risk_state",
    "ts_ms",
    "event_ts_ms",
    "processed_ts_ms",
    "raw_market_structure",
    "msl",
    "market_state",
    "risk_bias",
    "market_risk_state",
}


def _resolve_pointer(doc: Any, pointer: str) -> bool:
    if not pointer or pointer == "#":
        return True
    if not pointer.startswith("#/"):
        return False
    node = doc
    for token in pointer[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            return False
        node = node[token]
    return True


policy = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8")) or {}
errors: list[str] = []

version = policy.get("version")
if not isinstance(version, int):
    errors.append("version must be integer")

fields = policy.get("fields")
if not isinstance(fields, list) or not fields:
    errors.append("fields must be non-empty list")
    fields = []

seen: set[str] = set()
index: dict[str, dict[str, Any]] = {}
for i, item in enumerate(fields):
    if not isinstance(item, dict):
        errors.append(f"fields[{i}] must be object")
        continue
    name = str(item.get("name") or "").strip()
    if not name:
        errors.append(f"fields[{i}].name is required")
        continue
    if name in seen:
        errors.append(f"duplicated field name: {name}")
    seen.add(name)
    index[name] = item

    semantic = str(item.get("canonical_semantic") or "").strip()
    if not semantic:
        errors.append(f"field {name}: canonical_semantic is required")

    owner = str(item.get("owner") or "").strip()
    if owner and owner not in ALLOWED_OWNERS:
        errors.append(f"field {name}: unsupported owner '{owner}'")

    lifecycle = str(item.get("lifecycle") or "").strip()
    if lifecycle and lifecycle not in ALLOWED_LIFECYCLE:
        errors.append(f"field {name}: unsupported lifecycle '{lifecycle}'")

    for loc in item.get("allowed_locations") or []:
        if not isinstance(loc, str) or "#" not in loc:
            errors.append(f"field {name}: invalid location '{loc}'")
            continue
        schema_rel, pointer = loc.split("#", 1)
        schema_path = ROOT / schema_rel
        if not schema_path.is_file():
            errors.append(f"field {name}: missing schema '{schema_rel}'")
            continue
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"field {name}: invalid schema json '{schema_rel}': {exc}")
            continue
        if not _resolve_pointer(schema, f"#{pointer}"):
            errors.append(f"field {name}: unresolved pointer '{loc}'")

missing_required = sorted(REQUIRED_FIELDS - seen)
if missing_required:
    errors.append(f"missing required semantic fields: {missing_required}")

alias = index.get("confidence")
if alias:
    if alias.get("lifecycle") != "deprecated":
        errors.append("field confidence must be lifecycle=deprecated")
    sem = str(alias.get("canonical_semantic") or "")
    if "decision_confidence" not in sem:
        errors.append("field confidence canonical_semantic must reference decision_confidence")

risk_state = index.get("risk_state")
if risk_state and risk_state.get("expected_shape") != "enum":
    errors.append("field risk_state expected_shape must be enum")

ts_ms = index.get("ts_ms")
if ts_ms and ts_ms.get("expected_shape") != "integer":
    errors.append("field ts_ms expected_shape must be integer")

if errors:
    print("[failed] semantic policy guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

source_policy = yaml.safe_load(SOURCE_POLICY_PATH.read_text(encoding="utf-8")) or {}
if not isinstance(source_policy.get("version"), int):
    errors.append("source_semantics.version must be integer")

policies = source_policy.get("policies")
if not isinstance(policies, list) or not policies:
    errors.append("source_semantics.policies must be non-empty list")
    policies = []

target = None
for item in policies:
    if isinstance(item, dict) and str(item.get("name") or "").strip() == "alternative_sources_summary":
        target = item
        break
if not isinstance(target, dict):
    errors.append("source_semantics missing alternative_sources_summary policy")
    target = {}

required_keys = {str(x).strip() for x in list(target.get("required_keys") or []) if str(x).strip()}
expected_required_keys = {
    "available_sources",
    "unavailable_sources",
    "provider_states",
    "data_sources",
    "inference_sources",
    "feature_keys",
    "evidence_counts",
}
if not expected_required_keys.issubset(required_keys):
    errors.append(
        "source_semantics alternative_sources_summary.required_keys missing: "
        + str(sorted(expected_required_keys - required_keys))
    )

default_rules = target.get("default_rules") or {}
if not isinstance(default_rules, dict):
    errors.append("source_semantics alternative_sources_summary.default_rules must be object")
    default_rules = {}
for required_rule in (
    "event_center",
    "market_state_feature_fallback",
    "market_state_event_fallback",
    "agent_fusion_fallback",
):
    if required_rule not in default_rules:
        errors.append(f"source_semantics missing default_rules.{required_rule}")

if errors:
    print("[failed] semantic policy guard")
    for err in errors:
        print(f"- {err}")
    raise SystemExit(1)

print("[passed] semantic policy guard")
print(
    f"[info] policy={POLICY_PATH.relative_to(ROOT)} fields={len(fields)} required={len(REQUIRED_FIELDS)}; "
    f"source_policy={SOURCE_POLICY_PATH.relative_to(ROOT)}"
)
PY
