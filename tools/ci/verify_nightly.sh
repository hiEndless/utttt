#!/usr/bin/env bash
set -euo pipefail

echo "[nightly 1/8] structure guard"
bash tools/local/check_structure.sh
echo "[nightly 2/8] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[nightly 3/8] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[nightly 4/8] full verification suite"
bash tools/ci/verify_all.sh --report-json=verification/reports/nightly.latest.json
echo "[nightly 5/8] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[nightly 6/8] semantic audit"
bash tools/local/audit_semantics.sh
echo "[nightly 7/8] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
echo "[nightly 8/8] aggregate and check"
bash tools/local/aggregate_and_check.sh
