#!/usr/bin/env bash
set -euo pipefail

DOC="event_center_new/docs/ci.md"

echo "[1/2] 检查 CI 文档存在"
if ! test -f "$DOC"; then
  echo "[失败] 缺少 $DOC"
  exit 1
fi

echo "[2/2] 校验 CI 文档帮助快照关键行"
required_lines=(
  "当前帮助输出快照："
  "bash scripts/check_event_center_contract_guards.sh --quick"
  "bash scripts/check_event_center_contract_guards.sh [--quick] [--strict-wiring|--lenient-wiring]"
  "EC_GUARD_SCHEMA_FAILED"
  "EC_GUARD_RUNTIME_FAILED"
  "EC_GUARD_WIRING_FAILED"
  "EC_GUARD_CI_WORKFLOW_FAILED"
)

for line in "${required_lines[@]}"; do
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档帮助快照缺少关键行: $line"
    exit 1
  fi
done

echo "[通过] event_center CI 文档快照守卫检查完成。"
