#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) market_state_engine 不得恢复 feature 旧契约回退逻辑
# 2) 新契约行为测试必须通过

TARGET_FILE="market_state_engine/adapters/raw_structure_http.py"

echo "[1/2] 检查是否出现旧契约回退代码"
if rg -n 'data\.get\("raw_market_structure"\)' "${TARGET_FILE}" | rg -v 'data_block\.get\("raw_market_structure"\)'; then
  echo "[失败] 检测到顶层 raw_market_structure 回退解析，请移除。"
  exit 1
fi

if rg -n 'return dict\(data\.get\("data"\)' "${TARGET_FILE}"; then
  echo "[失败] 检测到 data 兜底回退解析，请移除。"
  exit 1
fi

echo "[2/2] 运行契约守卫测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q market_state_engine/text/test_raw_structure_http_provider_contract.py

echo "[通过] feature 契约守卫检查完成。"
