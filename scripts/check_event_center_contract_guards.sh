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

if [[ "$MODE" == "--quick" ]]; then
  echo "[1/3] event_center 契约/Schema 守卫（quick）"
  bash scripts/check_event_center_contract_schema_guards.sh --quick

  echo "[2/3] event_center Runtime 守卫（quick）"
  bash scripts/check_event_center_runtime_family_guards.sh --quick

  echo "[3/3] event_center 守卫接线检查（quick） mode=${WIRING_MODE#--}"
  bash scripts/check_event_center_guard_wiring.sh "$WIRING_MODE"
  echo "[通过] event_center 契约守卫检查完成（quick）。"
  exit 0
fi

echo "[1/3] event_center 契约/Schema 守卫（全量）"
bash scripts/check_event_center_contract_schema_guards.sh

echo "[2/3] event_center Runtime 守卫（全量）"
bash scripts/check_event_center_runtime_family_guards.sh

echo "[3/3] event_center 守卫接线检查（全量） mode=${WIRING_MODE#--}"
bash scripts/check_event_center_guard_wiring.sh "$WIRING_MODE"

echo "[通过] event_center 契约守卫检查完成。"
