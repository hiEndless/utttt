#!/usr/bin/env bash
set -euo pipefail

echo "[regression 1/8] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/8] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/8] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/8] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 5/8] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 6/8] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 7/8] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 8/8] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
