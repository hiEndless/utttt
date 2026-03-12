#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) market_state_engine 不得恢复 feature 旧契约回退逻辑
# 2) feature 合同入口版本声明必须与代码常量一致
# 3) feature 新契约行为测试必须通过

TARGET_FILE="services/market_state_engine/src/adapters/raw_structure_http.py"

echo "[1/3] 检查是否出现旧契约回退代码"
if rg -n 'data\.get\("raw_market_structure"\)' "${TARGET_FILE}" | rg -v 'data_block\.get\("raw_market_structure"\)'; then
  echo "[失败] 检测到顶层 raw_market_structure 回退解析，请移除。"
  exit 1
fi

if rg -n 'return dict\(data\.get\("data"\)' "${TARGET_FILE}"; then
  echo "[失败] 检测到 data 兜底回退解析，请移除。"
  exit 1
fi

echo "[2/3] 运行 feature 合同入口守卫"
bash tools/local/check_feature_contract_entry_guard.sh

echo "[3/3] 运行契约守卫测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/feature_service/test_feature_service_routes_contract.py

echo "[通过] feature 契约守卫检查完成。"
