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
  bash tools/local/check_new_arch_guards.sh
  bash tools/local/check_new_arch_guards.sh --event-center-only
  bash tools/local/check_new_arch_guards.sh --event-center-quick
  bash tools/local/check_new_arch_guards.sh --event-center-quick --lenient-wiring
说明:
  --strict-wiring/--lenient-wiring 仅影响 event_center 守卫接线检查策略。
  --event-center-only/--event-center-quick 都会先执行告警码入口守卫（check_alert_codes_entry_guard.sh）。
  除 --help 外，所有模式都会先执行跨服务时间语义文档守卫（check_cross_service_time_semantics_doc_guard.sh）。
  除 --help 外，所有模式都会先执行契约文档 canonical 布局守卫（check_contract_docs_canonical_layout_guard.sh）。
EOF
  exit 0
fi

# 跨服务时间语义文档一致性守卫：三种执行模式统一前置。
bash tools/local/check_cross_service_time_semantics_doc_guard.sh
# 契约文档 canonical 布局守卫：三种执行模式统一前置。
bash tools/local/check_contract_docs_canonical_layout_guard.sh

if [[ "$MODE" == "--event-center-only" ]]; then
  echo "[1/3] 告警码入口守卫"
  bash tools/local/check_alert_codes_entry_guard.sh
  echo "[2/3] event_center 契约聚合守卫（全量）"
  bash tools/local/check_event_center_contract_guards.sh "$WIRING_MODE"
  echo "[3/3] 新架构守卫检查完成（event_center-only）。"
  exit 0
fi

if [[ "$MODE" == "--event-center-quick" ]]; then
  echo "[1/3] 告警码入口守卫"
  bash tools/local/check_alert_codes_entry_guard.sh
  echo "[2/3] event_center 契约聚合守卫（quick）"
  bash tools/local/check_event_center_contract_guards.sh --quick "$WIRING_MODE"
  echo "[3/3] 新架构守卫检查完成（event_center-quick）。"
  exit 0
fi

bash tools/ci/new_arch_guards_full.sh "$WIRING_MODE"
