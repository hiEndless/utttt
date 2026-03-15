#!/usr/bin/env bash
set -euo pipefail

echo "[docs 1/14] semantic policy guard"
bash tools/local/check_semantic_policy_guard.sh

echo "[docs 2/14] source semantics guard"
bash tools/local/check_source_semantics_guard.sh

echo "[docs 3/14] cross-service time semantics doc guard"
bash tools/local/check_cross_service_time_semantics_doc_guard.sh

echo "[docs 4/14] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh

echo "[docs 5/14] direction enum doc guard"
bash tools/local/check_direction_enum_doc_guard.sh

echo "[docs 6/14] contract change bundle guard"
if ! bash tools/local/check_contract_change_bundle_guard.sh; then
  echo "[hint] 可执行以下命令输出版本探测值用于排障："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  exit 1
fi

echo "[docs 7/14] contract bundle regression tests"
./venv/bin/pytest -q verification/validators/contracts/test_contract_change_bundle_guard.py

echo "[docs 8/14] readme pipeline_mode quick path doc guards"
README_CONTRACTS_VERSION="$(
  ./venv/bin/python - <<'PY'
from verification.text.readme_contracts import README_CONTRACTS_VERSION
print(README_CONTRACTS_VERSION)
PY
)"
echo "[info] README_CONTRACTS_VERSION=$README_CONTRACTS_VERSION"
./venv/bin/pytest -q \
  verification/text/test_readme_contracts_path_normalization.py \
  verification/text/test_readme_contracts_version_format.py \
  verification/text/test_readme_contracts_version_baseline_format.py \
  verification/text/test_readme_contracts_version_monotonic.py \
  verification/text/test_readme_pipeline_mode_quick_paths.py \
  verification/text/test_cli_help_snapshot_readme_contract_version.py

echo "[docs 9/14] new_arch guards help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh

echo "[docs 10/14] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh

echo "[docs 11/14] release ready help snapshot guard"
bash tools/local/check_release_ready_help_snapshot_guard.sh

echo "[docs 12/14] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh

echo "[docs 13/14] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[docs 14/14] release docs repro alignment guard"
bash tools/local/check_release_docs_repro_alignment_guard.sh

echo "[passed] docs/contracts bundle guard check"
