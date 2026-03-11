#!/usr/bin/env bash
set -euo pipefail

bash tools/local/check_structure.sh
bash tools/ci/verify_all.sh --quick
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
