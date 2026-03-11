#!/usr/bin/env bash
set -euo pipefail

bash tools/local/check_structure.sh
bash tools/local/check_script_compat_whitelist.sh
bash tools/ci/verify_all.sh --report-json=verification/reports/nightly.latest.json
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
bash tools/local/check_semantic_warning_budget.sh
bash tools/local/aggregate_and_check.sh
