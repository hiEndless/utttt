#!/usr/bin/env bash
set -euo pipefail

bash tools/local/check_structure.sh
bash tools/local/check_script_compat_whitelist.sh
if ! bash tools/local/check_docs_contracts_bundle.sh; then
  echo "[hint] docs/contracts bundle 失败，建议执行："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  echo "[hint] 自动输出版本探测值（用于 CI 日志/artifact 排障）："
  bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions || true
  exit 1
fi
bash tools/local/check_release_baseline_alignment.sh
bash tools/ci/verify_all.sh --quick
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
bash tools/local/check_semantic_critical_warning_guard.sh
