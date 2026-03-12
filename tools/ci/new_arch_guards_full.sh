#!/usr/bin/env bash
set -euo pipefail

echo "[1/26] 新架构关键脚本纳管守卫"
bash tools/local/check_new_arch_tracked_scripts_guard.sh

echo "[2/26] 契约变更四件套守卫"
bash tools/local/check_contract_change_bundle_guard.sh

echo "[3/26] feature 契约守卫"
bash tools/local/check_feature_contract_guard.sh

echo "[4/26] feature 合同入口守卫"
bash tools/local/check_feature_contract_entry_guard.sh

echo "[5/26] feature schema 守卫"
bash tools/local/check_feature_service_schema_guard.sh

echo "[6/26] state 引擎守卫"
bash tools/local/check_market_state_engine_guard.sh

echo "[7/26] state 引擎 help 快照守卫"
bash tools/local/check_market_state_engine_help_snapshot_guard.sh

echo "[8/26] state->agent 联动守卫"
bash tools/local/check_state_to_agent_contract_guard.sh

echo "[9/26] runner 输出 schema 守卫"
bash tools/local/check_runner_output_schema_guard.sh

echo "[10/26] execution decision_intent schema 守卫"
bash tools/local/check_execution_decision_intent_schema_guard.sh

echo "[11/26] execution decision_state schema 守卫"
bash tools/local/check_execution_decision_state_schema_guard.sh

echo "[12/26] execution result schema 守卫"
bash tools/local/check_execution_result_schema_guard.sh

echo "[13/26] execution reconcile result schema 守卫"
bash tools/local/check_execution_reconcile_result_schema_guard.sh

echo "[14/26] execution retry_meta schema 守卫"
bash tools/local/check_execution_retry_meta_schema_guard.sh

echo "[15/26] execution signal_result schema 守卫"
bash tools/local/check_execution_signal_result_schema_guard.sh

echo "[16/26] execution risk_policy schema 守卫"
bash tools/local/check_execution_risk_policy_schema_guard.sh

echo "[17/26] execution schema mapping 守卫"
bash tools/local/check_execution_schema_mapping_guard.sh

echo "[18/26] execution breaking 升版守卫"
bash tools/local/check_execution_breaking_version_bump_guard.sh

echo "[19/26] execution 合同入口守卫"
bash tools/local/check_execution_contract_entry_guard.sh

echo "[20/26] market_state 合同入口守卫"
bash tools/local/check_market_state_contract_entry_guard.sh

echo "[21/26] event_center 合同入口守卫"
bash tools/local/check_event_center_contract_entry_guard.sh

echo "[22/26] contract docs index 守卫"
bash tools/local/check_contract_docs_index_guard.sh

echo "[23/26] contract docs index help 快照守卫"
bash tools/local/check_contract_docs_index_help_snapshot_guard.sh

echo "[24/26] agent->execution 联动守卫"
bash tools/local/check_agent_to_execution_guard.sh

echo "[25/26] 告警码入口守卫"
bash tools/local/check_alert_codes_entry_guard.sh

echo "[26/26] event_center 契约聚合守卫"
bash tools/local/check_event_center_contract_guards.sh "$@"

echo "[通过] 新架构守卫全量检查完成。"
