#!/usr/bin/env bash
set -euo pipefail

bash tools/ci/event_center_emit_meta_header.sh "event-center-quick-strict"
bash tools/ci/event_center_emit_guard_summary.sh quick strict
echo "[CI] event_center quick strict"
bash tools/local/check_new_arch_guards.sh --event-center-quick --strict-wiring
