#!/usr/bin/env bash
set -euo pipefail

bash scripts/ci_event_center_emit_meta_header.sh "event-center-quick-strict"
echo "[CI] event_center quick strict"
bash scripts/check_new_arch_guards.sh --event-center-quick --strict-wiring
