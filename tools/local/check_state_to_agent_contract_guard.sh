#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) 状态层与决策层核心实现不得回归 sentiment_state 依赖
# 2) 状态层与决策层的 MSL 契约测试必须通过

echo "[1/2] 检查核心实现是否回归 sentiment_state"
if rg -n "sentiment_state|SentimentState" \
  services/market_state_engine/src/contracts.py \
  services/market_state_engine/src/engine.py \
  services/market_state_engine/src/service.py \
  services/agent_server_new/adapters/market_state_http.py \
  services/agent_server_new/app/workflows/trade_event_workflow.py; then
  echo "[失败] 检测到核心实现回归 sentiment_state 依赖。"
  exit 1
fi

echo "[2/2] 运行状态层与决策层契约测试（含可追溯守卫）"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  verification/validators/market_state_engine \
  verification/auditors/agent_server_new/test_bootstrap.py \
  verification/auditors/agent_server_new/test_active_events_redis_adapter.py \
  verification/auditors/agent_server_new/test_active_events_contract_guard.py \
  verification/auditors/agent_server_new/test_pipeline_traceability_contract.py \
  verification/auditors/agent_server_new/test_runner.py \
  verification/auditors/agent_server_new/test_pipeline_smoke.py \
  verification/auditors/agent_server_new/test_market_state_msl_contract_consumer.py \
  verification/auditors/agent_server_new/test_market_state_snapshot_contract.py \
  verification/auditors/agent_server_new/test_horizon_policy_gate.py \
  verification/auditors/agent_server_new/test_runner_output_schema.py \
  verification/auditors/agent_server_new/test_trade_event_workflow_horizon_policy_gate.py \
  verification/auditors/agent_server_new/test_trade_event_workflow_execution_decider.py \
  verification/auditors/agent_server_new/test_trade_event_workflow_result.py

echo "[通过] state->agent 契约守卫检查完成（已覆盖 selected_event 可追溯链路）。"
