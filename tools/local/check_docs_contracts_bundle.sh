#!/usr/bin/env bash
set -euo pipefail

echo "[docs 1/4] semantic policy guard"
bash tools/local/check_semantic_policy_guard.sh

echo "[docs 2/4] cross-service time semantics doc guard"
bash tools/local/check_cross_service_time_semantics_doc_guard.sh

echo "[docs 3/4] new_arch guards help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh

echo "[docs 4/4] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh

echo "[passed] docs/contracts bundle guard check"
