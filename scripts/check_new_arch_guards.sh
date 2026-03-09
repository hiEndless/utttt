#!/usr/bin/env bash
set -euo pipefail

echo "[1/9] feature 契约守卫"
bash scripts/check_feature_contract_guard.sh

echo "[2/9] feature schema 守卫"
bash scripts/check_feature_service_schema_guard.sh

echo "[3/9] state 引擎守卫"
bash scripts/check_market_state_engine_guard.sh

echo "[4/9] state->agent 联动守卫"
bash scripts/check_state_to_agent_contract_guard.sh

echo "[5/9] runner 输出 schema 守卫"
bash scripts/check_runner_output_schema_guard.sh

echo "[6/9] execution decision_state schema 守卫"
bash scripts/check_execution_decision_state_schema_guard.sh

echo "[7/9] execution result schema 守卫"
bash scripts/check_execution_result_schema_guard.sh

echo "[8/9] contract docs index 守卫"
bash scripts/check_contract_docs_index_guard.sh

echo "[9/9] agent->execution 联动守卫"
bash scripts/check_agent_to_execution_guard.sh

echo "[通过] 新架构守卫全量检查完成。"
