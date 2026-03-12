#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
用法:
  bash tools/local/check_market_state_engine_guard.sh
  bash tools/local/check_market_state_engine_guard.sh --help

守卫目标:
  1) market_state_engine 核心实现不得回归 sentiment_state
  2) 状态层关键回归测试必须通过
EOF
  exit 0
fi

# 守卫目标：
# 1) market_state_engine 结构状态契约中不得回归 sentiment_state
# 2) 状态层关键测试保持通过

echo "[1/2] 检查状态层契约是否回归 sentiment_state"
if rg -n "sentiment_state|SentimentState" \
  services/market_state_engine/src/contracts.py \
  services/market_state_engine/src/engine.py \
  services/market_state_engine/src/service.py; then
  echo "[失败] 检测到 sentiment_state 回归到状态层核心实现。"
  exit 1
fi

echo "[2/2] 运行状态层回归测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  verification/validators/market_state_engine/test_market_state_data_unavailable.py \
  verification/validators/market_state_engine/test_raw_structure_http_provider_contract.py \
  verification/validators/market_state_engine/test_msl_contract_whitelist.py \
  verification/validators/market_state_engine/test_state_inference_pipeline.py

echo "[通过] market_state_engine 守卫检查完成。"
