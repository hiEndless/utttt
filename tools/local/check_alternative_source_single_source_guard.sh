#!/usr/bin/env bash
set -euo pipefail

TARGET_FILES=(
  "services/agent_server_new/app/context_builder.py"
  "services/market_state_engine/src/service.py"
  "services/event_center_new/ec/context/builder.py"
  "services/execution_service/adapters/agent_execution_plan_adapter.py"
  "services/execution_service/domain/contracts.py"
  "services/feature_service/src/providers/future_source_providers.py"
)

IMPORT_PATTERN='contracts\.schemas\.alternative_source_summary_contract'
HARDCODED_TUPLE_PATTERN='\("news",[[:space:]]*"social",[[:space:]]*"onchain"\)'

echo "[1/3] 检查目标文件存在"
for file in "${TARGET_FILES[@]}"; do
  if ! test -f "$file"; then
    echo "[失败] 缺少目标文件: $file"
    exit 1
  fi
done

echo "[2/3] 检查目标文件必须引用单源 contract helper"
for file in "${TARGET_FILES[@]}"; do
  if ! rg -n "$IMPORT_PATTERN" "$file" >/dev/null; then
    echo "[失败] 未检测到单源 helper 引用: $file"
    exit 1
  fi
done

echo "[3/3] 检查目标文件不得硬编码 news/social/onchain 三元组"
for file in "${TARGET_FILES[@]}"; do
  if rg -n "$HARDCODED_TUPLE_PATTERN" "$file" >/dev/null; then
    echo "[失败] 检测到硬编码三元组: $file"
    rg -n "$HARDCODED_TUPLE_PATTERN" "$file"
    exit 1
  fi
done

echo "[通过] alternative source 单源契约守卫检查完成。"
