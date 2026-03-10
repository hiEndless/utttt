#!/usr/bin/env bash
set -euo pipefail

echo "[1/18] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/18] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/18] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/18] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/18] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/18] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/18] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/18] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/18] execution reconcile result schema 守卫"
bash scripts/check_execution_reconcile_result_schema_guard.sh

echo "[10/18] execution retry_meta schema 守卫"
bash scripts/check_execution_retry_meta_schema_guard.sh

echo "[11/18] execution signal_result schema 守卫"
bash scripts/check_execution_signal_result_schema_guard.sh

echo "[12/18] execution risk_policy schema 守卫"
bash scripts/check_execution_risk_policy_schema_guard.sh

echo "[13/18] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[14/18] execution breaking 升版守卫"
bash scripts/check_execution_breaking_version_bump_guard.sh

echo "[15/18] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[16/18] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[17/18] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[18/18] event_center replay 守卫"
bash scripts/check_event_center_replay_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
