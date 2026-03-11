#!/usr/bin/env bash
set -euo pipefail

MODE="all"
WIRING_MODE="--strict-wiring"
for arg in "$@"; do
  case "$arg" in
    --help|-h)
      MODE="--help"
      ;;
    --event-center-only)
      MODE="--event-center-only"
      ;;
    --event-center-quick)
      MODE="--event-center-quick"
      ;;
    --strict-wiring)
      WIRING_MODE="--strict-wiring"
      ;;
    --lenient-wiring)
      WIRING_MODE="--lenient-wiring"
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
  bash scripts/check_new_arch_guards.sh
  bash scripts/check_new_arch_guards.sh --event-center-only
  bash scripts/check_new_arch_guards.sh --event-center-quick
  bash scripts/check_new_arch_guards.sh --event-center-quick --lenient-wiring
说明:
  --strict-wiring/--lenient-wiring 仅影响 event_center 守卫接线检查策略。
  --event-center-only/--event-center-quick 都会先执行告警码入口守卫（check_alert_codes_entry_guard.sh）。
EOF
  exit 0
fi

if [[ "$MODE" == "--event-center-only" ]]; then
  echo "[1/2] 告警码入口守卫"
  bash scripts/check_alert_codes_entry_guard.sh
  echo "[2/2] event_center 契约聚合守卫（全量）"
  bash scripts/check_event_center_contract_guards.sh "$WIRING_MODE"
  echo "[通过] 新架构守卫检查完成（event_center-only）。"
  exit 0
fi

if [[ "$MODE" == "--event-center-quick" ]]; then
  echo "[1/2] 告警码入口守卫"
  bash scripts/check_alert_codes_entry_guard.sh
  echo "[2/2] event_center 契约聚合守卫（quick）"
  bash scripts/check_event_center_contract_guards.sh --quick "$WIRING_MODE"
  echo "[通过] 新架构守卫检查完成（event_center-quick）。"
  exit 0
fi

bash tools/ci/new_arch_guards_full.sh "$WIRING_MODE"
