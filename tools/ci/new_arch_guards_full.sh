#!/usr/bin/env bash
set -euo pipefail

echo "[1/23] 新架构关键脚本纳管守卫"
bash tools/local/check_new_arch_tracked_scripts_guard.sh

echo "[2/23] feature 契约守卫"
bash tools/local/check_feature_contract_guard.sh

echo "[3/23] feature schema 守卫"
bash tools/local/check_feature_service_schema_guard.sh

echo "[4/23] state 引擎守卫"
bash tools/local/check_market_state_engine_guard.sh

echo "[5/23] state 引擎 help 快照守卫"
bash tools/local/check_market_state_engine_help_snapshot_guard.sh

echo "[6/23] state->agent 联动守卫"
bash tools/local/check_state_to_agent_contract_guard.sh

echo "[7/23] runner 输出 schema 守卫"
bash tools/local/check_runner_output_schema_guard.sh

echo "[8/23] execution decision_intent schema 守卫"
bash tools/local/check_execution_decision_intent_schema_guard.sh

echo "[9/23] execution decision_state schema 守卫"
bash tools/local/check_execution_decision_state_schema_guard.sh

echo "[10/23] execution result schema 守卫"
bash tools/local/check_execution_result_schema_guard.sh

echo "[11/23] execution reconcile result schema 守卫"
bash tools/local/check_execution_reconcile_result_schema_guard.sh

echo "[12/23] execution retry_meta schema 守卫"
bash tools/local/check_execution_retry_meta_schema_guard.sh

echo "[13/23] execution signal_result schema 守卫"
bash tools/local/check_execution_signal_result_schema_guard.sh

echo "[14/23] execution risk_policy schema 守卫"
bash tools/local/check_execution_risk_policy_schema_guard.sh

echo "[15/23] execution schema mapping 守卫"
bash tools/local/check_execution_schema_mapping_guard.sh

echo "[16/23] execution breaking 升版守卫"
bash tools/local/check_execution_breaking_version_bump_guard.sh

echo "[17/23] execution 合同入口守卫"
bash tools/local/check_execution_contract_entry_guard.sh

echo "[18/23] market_state 合同入口守卫"
bash tools/local/check_market_state_contract_entry_guard.sh

echo "[19/23] contract docs index 守卫"
bash tools/local/check_contract_docs_index_guard.sh

echo "[20/23] contract docs index help 快照守卫"
bash tools/local/check_contract_docs_index_help_snapshot_guard.sh

echo "[21/23] agent->execution 联动守卫"
bash tools/local/check_agent_to_execution_guard.sh

echo "[22/23] 告警码入口守卫"
bash tools/local/check_alert_codes_entry_guard.sh

echo "[23/23] event_center 契约聚合守卫"
bash tools/local/check_event_center_contract_guards.sh "$@"

echo "[通过] 新架构守卫全量检查完成。"
