#!/usr/bin/env bash
set -euo pipefail

bash tools/local/check_structure.sh
bash tools/local/check_script_compat_whitelist.sh
bash tools/local/check_semantic_policy_guard.sh
bash tools/local/check_cross_service_time_semantics_doc_guard.sh
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
bash tools/local/check_contract_docs_canonical_layout_guard.sh
bash tools/ci/verify_all.sh --quick
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
bash tools/local/check_semantic_critical_warning_guard.sh
