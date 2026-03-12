#!/usr/bin/env bash
set -euo pipefail

echo "[1/27] 新架构关键脚本纳管守卫"
bash tools/local/check_new_arch_tracked_scripts_guard.sh

echo "[2/27] 契约变更四件套守卫"
bash tools/local/check_contract_change_bundle_guard.sh

echo "[附加] 来源语义守卫"
bash tools/local/check_source_semantics_guard.sh

echo "[附加] alternative source 单源契约守卫"
bash tools/local/check_alternative_source_single_source_guard.sh

echo "[3/27] 发布基线对齐守卫"
bash tools/local/check_release_baseline_alignment.sh

echo "[4/27] feature 契约守卫"
bash tools/local/check_feature_contract_guard.sh

echo "[5/27] feature 合同入口守卫"
bash tools/local/check_feature_contract_entry_guard.sh

echo "[6/27] feature schema 守卫"
bash tools/local/check_feature_service_schema_guard.sh

echo "[7/27] state 引擎守卫"
bash tools/local/check_market_state_engine_guard.sh

echo "[8/27] state 引擎 help 快照守卫"
bash tools/local/check_market_state_engine_help_snapshot_guard.sh

echo "[9/27] state->agent 联动守卫"
bash tools/local/check_state_to_agent_contract_guard.sh

echo "[10/27] runner 输出 schema 守卫"
bash tools/local/check_runner_output_schema_guard.sh

echo "[11/27] execution decision_intent schema 守卫"
bash tools/local/check_execution_decision_intent_schema_guard.sh

echo "[12/27] execution decision_state schema 守卫"
bash tools/local/check_execution_decision_state_schema_guard.sh

echo "[13/27] execution result schema 守卫"
bash tools/local/check_execution_result_schema_guard.sh

echo "[14/27] execution reconcile result schema 守卫"
bash tools/local/check_execution_reconcile_result_schema_guard.sh

echo "[15/27] execution retry_meta schema 守卫"
bash tools/local/check_execution_retry_meta_schema_guard.sh

echo "[16/27] execution signal_result schema 守卫"
bash tools/local/check_execution_signal_result_schema_guard.sh

echo "[17/27] execution risk_policy schema 守卫"
bash tools/local/check_execution_risk_policy_schema_guard.sh

echo "[18/27] execution schema mapping 守卫"
bash tools/local/check_execution_schema_mapping_guard.sh

echo "[19/27] execution breaking 升版守卫"
bash tools/local/check_execution_breaking_version_bump_guard.sh

echo "[20/27] execution 合同入口守卫"
bash tools/local/check_execution_contract_entry_guard.sh

echo "[21/27] market_state 合同入口守卫"
bash tools/local/check_market_state_contract_entry_guard.sh

echo "[22/27] event_center 合同入口守卫"
bash tools/local/check_event_center_contract_entry_guard.sh

echo "[23/27] contract docs index 守卫"
bash tools/local/check_contract_docs_index_guard.sh

echo "[24/27] contract docs index help 快照守卫"
bash tools/local/check_contract_docs_index_help_snapshot_guard.sh

echo "[25/27] agent->execution 联动守卫"
bash tools/local/check_agent_to_execution_guard.sh

echo "[26/27] 告警码入口守卫"
bash tools/local/check_alert_codes_entry_guard.sh

echo "[27/27] event_center 契约聚合守卫"
bash tools/local/check_event_center_contract_guards.sh "$@"

echo "[通过] 新架构守卫全量检查完成。"
