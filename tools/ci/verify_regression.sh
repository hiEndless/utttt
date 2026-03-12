#!/usr/bin/env bash
set -euo pipefail

echo "[regression 1/11] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/11] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/11] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/11] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[regression 5/11] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 6/11] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh
echo "[regression 7/11] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 8/11] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[regression 9/11] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 10/11] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 11/11] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
