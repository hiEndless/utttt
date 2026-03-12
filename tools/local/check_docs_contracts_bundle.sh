#!/usr/bin/env bash
set -euo pipefail

echo "[docs 1/7] semantic policy guard"
bash tools/local/check_semantic_policy_guard.sh

echo "[docs 2/7] cross-service time semantics doc guard"
bash tools/local/check_cross_service_time_semantics_doc_guard.sh

echo "[docs 3/7] contract change bundle guard"
if ! bash tools/local/check_contract_change_bundle_guard.sh; then
  echo "[hint] 可执行以下命令输出版本探测值用于排障："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  exit 1
fi

echo "[docs 4/7] contract bundle regression tests"
./venv/bin/pytest -q verification/validators/contracts/test_contract_change_bundle_guard.py

echo "[docs 5/7] new_arch guards help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh

echo "[docs 6/7] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh

echo "[docs 7/7] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[passed] docs/contracts bundle guard check"
