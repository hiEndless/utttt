#!/usr/bin/env bash
set -euo pipefail

echo "[docs 1/13] semantic policy guard"
bash tools/local/check_semantic_policy_guard.sh

echo "[docs 2/13] source semantics guard"
bash tools/local/check_source_semantics_guard.sh

echo "[docs 3/13] cross-service time semantics doc guard"
bash tools/local/check_cross_service_time_semantics_doc_guard.sh

echo "[docs 4/13] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh

echo "[docs 5/13] contract change bundle guard"
if ! bash tools/local/check_contract_change_bundle_guard.sh; then
  echo "[hint] 可执行以下命令输出版本探测值用于排障："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  exit 1
fi

echo "[docs 6/13] contract bundle regression tests"
./venv/bin/pytest -q verification/validators/contracts/test_contract_change_bundle_guard.py

echo "[docs 7/13] readme pipeline_mode quick path doc guards"
./venv/bin/pytest -q \
  verification/text/test_agent_readme_pipeline_mode_quick_path.py \
  verification/text/test_verification_reports_readme_pipeline_mode_quick_path.py

echo "[docs 8/13] new_arch guards help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh

echo "[docs 9/13] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh

echo "[docs 10/13] release ready help snapshot guard"
bash tools/local/check_release_ready_help_snapshot_guard.sh

echo "[docs 11/13] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh

echo "[docs 12/13] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[docs 13/13] release docs repro alignment guard"
bash tools/local/check_release_docs_repro_alignment_guard.sh

echo "[passed] docs/contracts bundle guard check"
