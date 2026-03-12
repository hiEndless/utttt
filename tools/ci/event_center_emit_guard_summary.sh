#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-quick}"
WIRING_MODE="${2:-strict}"

if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  echo "[失败] 不支持的 MODE: $MODE（仅支持 quick/full）"
  exit 1
fi

if [[ "$WIRING_MODE" != "strict" && "$WIRING_MODE" != "lenient" ]]; then
  echo "[失败] 不支持的 WIRING_MODE: $WIRING_MODE（仅支持 strict/lenient）"
  exit 1
fi

layer_store_mode="$(printf '%s' "${EVENT_CENTER_LAYER_STORE_MODE:-memory}" | tr '[:upper:]' '[:lower:]')"
run_loop="$(printf '%s' "${EVENT_CENTER_RUN_LOOP:-false}" | tr '[:upper:]' '[:lower:]')"
self_check_only="$(printf '%s' "${EVENT_CENTER_SELF_CHECK_ONLY:-false}" | tr '[:upper:]' '[:lower:]')"
stop_on_error="$(printf '%s' "${EVENT_CENTER_STOP_ON_ERROR:-false}" | tr '[:upper:]' '[:lower:]')"
run_interval_ms="${EVENT_CENTER_RUN_INTERVAL_MS:-1000}"
run_max_ticks="${EVENT_CENTER_RUN_MAX_TICKS:-0}"
health_key="${EVENT_CENTER_HEALTH_KEY:-ec:runner:health}"
redis_url_set="false"
if [[ -n "${EVENT_CENTER_REDIS_URL:-}" ]]; then
  redis_url_set="true"
fi

echo "[CI_GUARD] contract_guard_mode=${MODE}"
echo "[CI_GUARD] wiring_mode=${WIRING_MODE}"
echo "[CI_GUARD] replay_strict_ci_guard=true"
echo "[CI_GUARD] runtime_mode_guard=true"
echo "[CI_GUARD] runtime.layer_store_mode=${layer_store_mode}"
echo "[CI_GUARD] runtime.run_loop=${run_loop}"
echo "[CI_GUARD] runtime.self_check_only=${self_check_only}"
echo "[CI_GUARD] runtime.stop_on_error=${stop_on_error}"
echo "[CI_GUARD] runtime.run_interval_ms=${run_interval_ms}"
echo "[CI_GUARD] runtime.run_max_ticks=${run_max_ticks}"
echo "[CI_GUARD] runtime.health_key=${health_key}"
echo "[CI_GUARD] runtime.redis_url_set=${redis_url_set}"
