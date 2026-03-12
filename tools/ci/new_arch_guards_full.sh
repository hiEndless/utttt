#!/usr/bin/env bash
set -euo pipefail

echo "[1/24] 新架构关键脚本纳管守卫"
bash tools/local/check_new_arch_tracked_scripts_guard.sh

echo "[2/24] feature 契约守卫"
bash tools/local/check_feature_contract_guard.sh

echo "[3/24] feature 合同入口守卫"
bash tools/local/check_feature_contract_entry_guard.sh

echo "[4/24] feature schema 守卫"
bash tools/local/check_feature_service_schema_guard.sh

echo "[5/24] state 引擎守卫"
bash tools/local/check_market_state_engine_guard.sh

echo "[6/24] state 引擎 help 快照守卫"
bash tools/local/check_market_state_engine_help_snapshot_guard.sh

echo "[7/24] state->agent 联动守卫"
bash tools/local/check_state_to_agent_contract_guard.sh

echo "[8/24] runner 输出 schema 守卫"
bash tools/local/check_runner_output_schema_guard.sh

echo "[9/24] execution decision_intent schema 守卫"
bash tools/local/check_execution_decision_intent_schema_guard.sh

echo "[10/24] execution decision_state schema 守卫"
bash tools/local/check_execution_decision_state_schema_guard.sh

echo "[11/24] execution result schema 守卫"
bash tools/local/check_execution_result_schema_guard.sh

echo "[12/24] execution reconcile result schema 守卫"
bash tools/local/check_execution_reconcile_result_schema_guard.sh

echo "[13/24] execution retry_meta schema 守卫"
bash tools/local/check_execution_retry_meta_schema_guard.sh

echo "[14/24] execution signal_result schema 守卫"
bash tools/local/check_execution_signal_result_schema_guard.sh

echo "[15/24] execution risk_policy schema 守卫"
bash tools/local/check_execution_risk_policy_schema_guard.sh

echo "[16/24] execution schema mapping 守卫"
bash tools/local/check_execution_schema_mapping_guard.sh

echo "[17/24] execution breaking 升版守卫"
bash tools/local/check_execution_breaking_version_bump_guard.sh

echo "[18/24] execution 合同入口守卫"
bash tools/local/check_execution_contract_entry_guard.sh

echo "[19/24] market_state 合同入口守卫"
bash tools/local/check_market_state_contract_entry_guard.sh

echo "[20/24] contract docs index 守卫"
bash tools/local/check_contract_docs_index_guard.sh

echo "[21/24] contract docs index help 快照守卫"
bash tools/local/check_contract_docs_index_help_snapshot_guard.sh

echo "[22/24] agent->execution 联动守卫"
bash tools/local/check_agent_to_execution_guard.sh

echo "[23/24] 告警码入口守卫"
bash tools/local/check_alert_codes_entry_guard.sh

echo "[24/24] event_center 契约聚合守卫"
bash tools/local/check_event_center_contract_guards.sh "$@"

echo "[通过] 新架构守卫全量检查完成。"
