#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 关键新架构脚本必须纳入版本管理，避免“本地可跑但仓库未纳管”。

REQUIRED_SCRIPTS=(
  "tools/local/check_feature_contract_guard.sh"
  "tools/local/check_feature_contract_entry_guard.sh"
  "tools/local/check_feature_service_schema_guard.sh"
  "tools/local/check_market_state_contract_entry_guard.sh"
  "tools/local/check_event_center_contract_entry_guard.sh"
  "tools/local/check_runner_output_schema_guard.sh"
  "tools/local/integration_smoke_new_arch.sh"
)

echo "[1/2] 检查关键脚本文件存在"
for path in "${REQUIRED_SCRIPTS[@]}"; do
  if [[ ! -f "${path}" ]]; then
    echo "[失败] 缺少关键脚本: ${path}"
    exit 1
  fi
done

echo "[2/2] 检查关键脚本已纳入版本管理"
for path in "${REQUIRED_SCRIPTS[@]}"; do
  if ! git ls-files --error-unmatch "${path}" >/dev/null 2>&1; then
    echo "[失败] 脚本未纳入版本管理: ${path}"
    echo "请执行: git add ${path}"
    exit 1
  fi
done

echo "[通过] 新架构关键脚本纳管守卫检查完成。"
