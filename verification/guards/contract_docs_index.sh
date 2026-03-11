#!/usr/bin/env bash
set -euo pipefail

bash scripts/check_contract_docs_index_guard.sh
bash scripts/check_contract_docs_index_help_snapshot_guard.sh
