#!/usr/bin/env bash
set -euo pipefail

echo "[nightly 1/12] structure guard"
bash tools/local/check_structure.sh
echo "[nightly 2/12] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[nightly 3/12] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[nightly 4/12] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[nightly 5/12] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[nightly 6/12] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh
echo "[nightly 7/12] full verification suite"
bash tools/ci/verify_all.sh --report-json=verification/reports/nightly.latest.json
echo "[nightly 8/12] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[nightly 9/12] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[nightly 10/12] semantic audit"
bash tools/local/audit_semantics.sh
echo "[nightly 11/12] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
echo "[nightly 12/12] aggregate and check"
MAX_LEGACY_CONFIDENCE_RATIO="${MAX_LEGACY_CONFIDENCE_RATIO:-0.05}"
echo "[nightly] MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
bash tools/local/aggregate_and_check.sh --max-legacy-confidence-ratio "$MAX_LEGACY_CONFIDENCE_RATIO"
