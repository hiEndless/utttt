#!/usr/bin/env bash
set -euo pipefail

echo "[CI] event_center quick strict"
bash scripts/check_new_arch_guards.sh --event-center-quick --strict-wiring
