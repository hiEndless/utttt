#!/usr/bin/env bash
set -euo pipefail

echo "[regression 1/7] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/7] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/7] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/7] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 5/7] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 6/7] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 7/7] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
