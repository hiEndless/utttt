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

echo "[1/19] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/19] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/19] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/19] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/19] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/19] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/19] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/19] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/19] execution reconcile result schema 守卫"
bash scripts/check_execution_reconcile_result_schema_guard.sh

echo "[10/19] execution retry_meta schema 守卫"
bash scripts/check_execution_retry_meta_schema_guard.sh

echo "[11/19] execution signal_result schema 守卫"
bash scripts/check_execution_signal_result_schema_guard.sh

echo "[12/19] execution risk_policy schema 守卫"
bash scripts/check_execution_risk_policy_schema_guard.sh

echo "[13/19] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[14/19] execution breaking 升版守卫"
bash scripts/check_execution_breaking_version_bump_guard.sh

echo "[15/19] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[16/19] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[17/19] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[18/19] 告警码入口守卫"
bash scripts/check_alert_codes_entry_guard.sh

echo "[19/19] event_center 契约聚合守卫"
bash scripts/check_event_center_contract_guards.sh "$WIRING_MODE"

echo "[通过] 新架构守卫全量检查完成。"
