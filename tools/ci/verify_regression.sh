#!/usr/bin/env bash
set -euo pipefail

echo "[regression 1/10] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/10] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/10] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/10] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[regression 5/10] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 6/10] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 7/10] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[regression 8/10] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 9/10] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 10/10] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
