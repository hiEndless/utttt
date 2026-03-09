#!/usr/bin/env bash
set -euo pipefail

echo "[1/17] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/17] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/17] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/17] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/17] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/17] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/17] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/17] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/17] execution reconcile result schema 守卫"
bash scripts/check_execution_reconcile_result_schema_guard.sh

echo "[10/17] execution retry_meta schema 守卫"
bash scripts/check_execution_retry_meta_schema_guard.sh

echo "[11/17] execution signal_result schema 守卫"
bash scripts/check_execution_signal_result_schema_guard.sh

echo "[12/17] execution risk_policy schema 守卫"
bash scripts/check_execution_risk_policy_schema_guard.sh

echo "[13/17] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[14/17] execution breaking 升版守卫"
bash scripts/check_execution_breaking_version_bump_guard.sh

echo "[15/17] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[16/17] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[17/17] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
