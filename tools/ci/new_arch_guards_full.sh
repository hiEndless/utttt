#!/usr/bin/env bash
set -euo pipefail

echo "[1/22] 新架构关键脚本纳管守卫"
bash scripts/check_new_arch_tracked_scripts_guard.sh

echo "[2/22] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[3/22] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[4/22] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[5/22] state 引擎 help 快照守卫"
bash scripts/check_market_state_engine_help_snapshot_guard.sh

echo "[6/22] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[7/22] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[8/22] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[9/22] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[10/22] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[11/22] execution reconcile result schema 守卫"
bash scripts/check_execution_reconcile_result_schema_guard.sh

echo "[12/22] execution retry_meta schema 守卫"
bash scripts/check_execution_retry_meta_schema_guard.sh

echo "[13/22] execution signal_result schema 守卫"
bash scripts/check_execution_signal_result_schema_guard.sh

echo "[14/22] execution risk_policy schema 守卫"
bash scripts/check_execution_risk_policy_schema_guard.sh

echo "[15/22] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[16/22] execution breaking 升版守卫"
bash scripts/check_execution_breaking_version_bump_guard.sh

echo "[17/22] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[18/22] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[19/22] contract docs index help 快照守卫"
bash scripts/check_contract_docs_index_help_snapshot_guard.sh

echo "[20/22] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[21/22] 告警码入口守卫"
bash scripts/check_alert_codes_entry_guard.sh

echo "[22/22] event_center 契约聚合守卫"
bash scripts/check_event_center_contract_guards.sh "$@"

echo "[通过] 新架构守卫全量检查完成。"
