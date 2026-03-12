#!/usr/bin/env bash
set -euo pipefail

echo "[regression 1/9] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/9] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/9] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/9] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[regression 5/9] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 6/9] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick
echo "[regression 7/9] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 8/9] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 9/9] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
