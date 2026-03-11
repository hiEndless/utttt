#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

bash tools/local/check_services_map_consistency.sh

required_dirs=(
  "services"
  "contracts"
  "contracts/schemas"
  "contracts/mappings"
  "contracts/semantic_policies"
  "contracts/versions"
  "verification"
  "verification/validators"
  "verification/guards"
  "verification/replay"
  "verification/diff"
  "verification/auditors"
  "verification/reports"
  "fixtures"
  "fixtures/contract_cases"
  "fixtures/replay_cases"
  "fixtures/workflow_cases"
  "fixtures/snapshots"
  "tools"
  "tools/ci"
  "tools/local"
  "docs"
  "docs/architecture"
  "docs/contracts"
  "docs/operations"
)

missing=0
echo "[check] required directory skeleton"
for d in "${required_dirs[@]}"; do
  if [[ -d "$d" ]]; then
    echo "[ok] $d"
  else
    echo "[missing] $d"
    missing=1
  fi
done

echo "[check] service scaffold placeholders"
for s in feature_service market_state_engine event_center_new agent_server_new execution_service; do
  p="services/$s/README.md"
  if [[ -f "$p" ]]; then
    echo "[ok] $p"
  else
    echo "[missing] $p"
    missing=1
  fi
done

echo "[check] service soft entrypoints"
soft_entrypoints=(
  "services/feature_service/main.py"
  "services/market_state_engine/main.py"
  "services/event_center_new/main.py"
  "services/event_center_new/replay_main.py"
  "services/agent_server_new/main.py"
  "services/agent_server_new/pipeline_smoke.py"
  "services/agent_server_new/memory_summary_runner.py"
  "services/execution_service/main.py"
)
for p in "${soft_entrypoints[@]}"; do
  if [[ -f "$p" ]]; then
    echo "[ok] $p"
  else
    echo "[missing] $p"
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  echo "[failed] structure skeleton check failed"
  exit 1
fi

echo "[passed] structure skeleton check passed"
