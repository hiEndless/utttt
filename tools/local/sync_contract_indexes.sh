#!/usr/bin/env bash
set -euo pipefail

bash tools/local/sync_contract_schemas.sh
bash tools/local/sync_contract_mappings.sh
