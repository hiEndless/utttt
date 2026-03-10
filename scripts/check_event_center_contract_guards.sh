#!/usr/bin/env bash
set -euo pipefail

MODE="all"
WIRING_MODE="--strict"
for arg in "$@"; do
  case "$arg" in
    --quick)
      MODE="--quick"
      ;;
    --strict-wiring)
      WIRING_MODE="--strict"
      ;;
    --lenient-wiring)
      WIRING_MODE="--lenient"
      ;;
    --help|-h)
      MODE="--help"
      ;;
    *)
      echo "[失败] 不支持的参数: $arg"
      echo "使用 --help 查看可用参数。"
      exit 1
      ;;
  esac
done

if [[ "$MODE" == "--help" ]]; then
  cat <<'EOF'
用法:
  bash scripts/check_event_center_contract_guards.sh
  bash scripts/check_event_center_contract_guards.sh --quick
  bash scripts/check_event_center_contract_guards.sh [--quick] [--strict-wiring|--lenient-wiring]
EOF
  exit 0
fi

run_guard() {
  local label="$1"
  local fail_code="$2"
  shift 2
  echo "$label"
  if ! "$@"; then
    echo "[失败] FAIL_CODE=$fail_code"
    return 1
  fi
}

if [[ "$MODE" == "--quick" ]]; then
  run_guard \
    "[1/4] event_center 契约/Schema 守卫（quick）" \
    "EC_GUARD_SCHEMA_FAILED" \
    bash scripts/check_event_center_contract_schema_guards.sh --quick

  run_guard \
    "[2/4] event_center Runtime 守卫（quick）" \
    "EC_GUARD_RUNTIME_FAILED" \
    bash scripts/check_event_center_runtime_family_guards.sh --quick

  run_guard \
    "[3/4] event_center 守卫接线检查（quick） mode=${WIRING_MODE#--}" \
    "EC_GUARD_WIRING_FAILED" \
    bash scripts/check_event_center_guard_wiring.sh "$WIRING_MODE"

  run_guard \
    "[4/4] event_center CI workflow 守卫（quick）" \
    "EC_GUARD_CI_WORKFLOW_FAILED" \
    bash scripts/check_event_center_ci_workflow_guard.sh
  echo "[通过] event_center 契约守卫检查完成（quick）。"
  exit 0
fi

run_guard \
  "[1/4] event_center 契约/Schema 守卫（全量）" \
  "EC_GUARD_SCHEMA_FAILED" \
  bash scripts/check_event_center_contract_schema_guards.sh
run_guard \
  "[2/4] event_center Runtime 守卫（全量）" \
  "EC_GUARD_RUNTIME_FAILED" \
  bash scripts/check_event_center_runtime_family_guards.sh
run_guard \
  "[3/4] event_center 守卫接线检查（全量） mode=${WIRING_MODE#--}" \
  "EC_GUARD_WIRING_FAILED" \
  bash scripts/check_event_center_guard_wiring.sh "$WIRING_MODE"
run_guard \
  "[4/4] event_center CI workflow 守卫（全量）" \
  "EC_GUARD_CI_WORKFLOW_FAILED" \
  bash scripts/check_event_center_ci_workflow_guard.sh

echo "[通过] event_center 契约守卫检查完成。"
