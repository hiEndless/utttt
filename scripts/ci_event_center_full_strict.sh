#!/usr/bin/env bash
set -euo pipefail

bash scripts/ci_event_center_emit_meta_header.sh "event-center-full-strict"
echo "[CI] event_center full strict"
bash scripts/check_new_arch_guards.sh --event-center-only --strict-wiring
