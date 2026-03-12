#!/usr/bin/env bash
set -euo pipefail

echo "[docs 1/6] semantic policy guard"
bash tools/local/check_semantic_policy_guard.sh

echo "[docs 2/6] cross-service time semantics doc guard"
bash tools/local/check_cross_service_time_semantics_doc_guard.sh

echo "[docs 3/6] contract change bundle guard"
bash tools/local/check_contract_change_bundle_guard.sh

echo "[docs 4/6] contract bundle regression tests"
./venv/bin/pytest -q verification/validators/contracts/test_contract_change_bundle_guard.py

echo "[docs 5/6] new_arch guards help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh

echo "[docs 6/6] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh

echo "[passed] docs/contracts bundle guard check"
