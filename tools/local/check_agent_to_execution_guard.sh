#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) agent->execution 适配器必须存在
# 2) execution 契约与最小联调测试必须通过

echo "[1/2] 检查 agent->execution 适配器是否存在"
if ! test -f services/execution_service/adapters/agent_execution_plan_adapter.py; then
  echo "[失败] 缺少 services/execution_service/adapters/agent_execution_plan_adapter.py"
  exit 1
fi

echo "[2/2] 运行 execution 契约与联调测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  verification/validators/execution_service/test_decision_intent_contract.py \
  verification/validators/execution_service/test_execution_decision_engine.py \
  verification/validators/execution_service/test_execution_api.py \
  verification/validators/execution_service/test_execution_idempotency.py \
  verification/validators/execution_service/test_execution_state_machine.py \
  verification/validators/execution_service/test_execution_submit_flow.py \
  verification/validators/execution_service/test_exchange_execution_sink.py \
  verification/validators/execution_service/test_execution_reconcile_retry.py \
  verification/validators/execution_service/test_execution_reconcile_result_schema.py \
  verification/validators/execution_service/test_retry_meta_schema.py \
  verification/validators/execution_service/test_reconcile_reason_codes_contract.py \
  verification/validators/execution_service/test_reconcile_status_codes_contract.py \
  verification/validators/execution_service/test_retry_meta_contract.py \
  verification/validators/execution_service/test_decision_intent_schema.py \
  verification/validators/execution_service/test_decision_state_schema.py \
  verification/validators/execution_service/test_execution_result_schema.py \
  verification/validators/execution_service/test_execution_signal_result_schema.py \
  verification/validators/execution_service/test_risk_check_codes_contract.py \
  verification/validators/execution_service/test_risk_check_meta_contract.py \
  verification/validators/execution_service/test_risk_check_message_templates.py \
  verification/validators/execution_service/test_risk_check_builder.py \
  verification/validators/execution_service/test_risk_result_builder.py \
  verification/validators/execution_service/test_risk_policy_schema.py \
  verification/validators/execution_service/test_risk_policy_providers.py \
  verification/validators/execution_service/test_schema_mapping.py \
  verification/validators/execution_service/test_stub_state_providers.py \
  verification/validators/execution_service/test_agent_to_execution_smoke.py \
  verification/validators/execution_service/test_redis_state_providers.py \
  verification/validators/execution_service/test_execution_app_provider_mode.py

echo "[通过] agent->execution 契约守卫检查完成。"
