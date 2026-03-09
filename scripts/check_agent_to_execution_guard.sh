#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) agent->execution 适配器必须存在
# 2) execution 契约与最小联调测试必须通过

echo "[1/2] 检查 agent->execution 适配器是否存在"
if ! test -f execution_service/adapters/agent_execution_plan_adapter.py; then
  echo "[失败] 缺少 execution_service/adapters/agent_execution_plan_adapter.py"
  exit 1
fi

echo "[2/2] 运行 execution 契约与联调测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  execution_service/text/test_decision_intent_contract.py \
  execution_service/text/test_execution_decision_engine.py \
  execution_service/text/test_execution_api.py \
  execution_service/text/test_execution_idempotency.py \
  execution_service/text/test_execution_state_machine.py \
  execution_service/text/test_execution_submit_flow.py \
  execution_service/text/test_execution_reconcile_retry.py \
  execution_service/text/test_execution_reconcile_result_schema.py \
  execution_service/text/test_decision_intent_schema.py \
  execution_service/text/test_decision_state_schema.py \
  execution_service/text/test_execution_result_schema.py \
  execution_service/text/test_schema_mapping.py \
  execution_service/text/test_stub_state_providers.py \
  execution_service/text/test_agent_to_execution_smoke.py \
  execution_service/text/test_redis_state_providers.py \
  execution_service/text/test_execution_app_provider_mode.py

echo "[通过] agent->execution 契约守卫检查完成。"
