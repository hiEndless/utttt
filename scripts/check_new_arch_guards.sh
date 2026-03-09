#!/usr/bin/env bash
set -euo pipefail

echo "[1/12] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/12] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/12] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/12] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/12] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/12] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/12] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/12] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/12] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[10/12] execution 合同入口守卫"
bash scripts/check_execution_contract_entry_guard.sh

echo "[11/12] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[12/12] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
