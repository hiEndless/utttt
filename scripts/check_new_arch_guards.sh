#!/usr/bin/env bash
set -euo pipefail

echo "[1/11] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/11] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/11] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/11] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/11] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/11] execution decision_intent schema 守卫"
bash scripts/check_execution_decision_intent_schema_guard.sh

echo "[7/11] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[8/11] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[9/11] execution schema mapping 守卫"
bash scripts/check_execution_schema_mapping_guard.sh

echo "[10/11] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[11/11] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
