#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_regression.sh

Description:
  CI regression 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、event-center quick 回归链路与语义审计。

Failure Codes:
  exit 1  任一守卫/测试失败
USAGE
  exit 0
fi

if (($# > 0)); then
  echo "[failed] unsupported args: $*"
  echo "hint: run 'bash tools/ci/verify_regression.sh --help'"
  exit 1
fi

echo "[regression 1/12] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/12] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/12] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/12] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[regression 5/12] ci help smoke tests"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q verification/text/test_verify_ci_help.py
else
  python3 -m pytest -q verification/text/test_verify_ci_help.py
fi
echo "[regression 6/12] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 7/12] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh
echo "[regression 8/12] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 9/12] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[regression 10/12] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 11/12] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 12/12] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
