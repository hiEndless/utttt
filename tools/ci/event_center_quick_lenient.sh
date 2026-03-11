#!/usr/bin/env bash
set -euo pipefail

bash tools/ci/event_center_emit_meta_header.sh "event-center-quick-lenient"
echo "[CI] event_center quick lenient"
bash scripts/check_new_arch_guards.sh --event-center-quick --lenient-wiring
