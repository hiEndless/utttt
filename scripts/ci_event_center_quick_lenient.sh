#!/usr/bin/env bash
set -euo pipefail

echo "[CI] event_center quick lenient"
bash scripts/check_new_arch_guards.sh --event-center-quick --lenient-wiring
