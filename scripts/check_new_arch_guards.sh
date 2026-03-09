#!/usr/bin/env bash
set -euo pipefail

echo "[1/16] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/16] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/16] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/16] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/16] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/16] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/16] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/16] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/16] execution reconcile result schema 守卫"
bash scripts/check_execution_reconcile_result_schema_guard.sh

echo "[10/16] execution retry_meta schema 守卫"
bash scripts/check_execution_retry_meta_schema_guard.sh

echo "[11/16] execution signal_result schema 守卫"
bash scripts/check_execution_signal_result_schema_guard.sh

echo "[12/16] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[13/16] execution breaking 升版守卫"
bash scripts/check_execution_breaking_version_bump_guard.sh

echo "[14/16] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[15/16] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[16/16] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
