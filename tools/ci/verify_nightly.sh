#!/usr/bin/env bash
set -euo pipefail

echo "[nightly 1/10] structure guard"
bash tools/local/check_structure.sh
echo "[nightly 2/10] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[nightly 3/10] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[nightly 4/10] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[nightly 5/10] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[nightly 6/10] full verification suite"
bash tools/ci/verify_all.sh --report-json=verification/reports/nightly.latest.json
echo "[nightly 7/10] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[nightly 8/10] semantic audit"
bash tools/local/audit_semantics.sh
echo "[nightly 9/10] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
echo "[nightly 10/10] aggregate and check"
bash tools/local/aggregate_and_check.sh
