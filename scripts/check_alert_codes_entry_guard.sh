#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 检查告警码文档存在"
if ! test -f docs/ALERT_CODES.md; then
  echo "[失败] 缺少 docs/ALERT_CODES.md"
  exit 1
fi

echo "[2/3] 检查 CONTRACT_INDEX 已收录告警码文档"
if ! rg -q "docs/ALERT_CODES.md" docs/CONTRACT_INDEX.md; then
  echo "[失败] docs/CONTRACT_INDEX.md 未收录 docs/ALERT_CODES.md"
  exit 1
fi

echo "[3/3] 检查三模块 README 已链接告警码文档"
for f in market_state_engine/README.md event_center_new/README.md agent_server_new/README.md; do
  if ! rg -q "docs/ALERT_CODES.md" "$f"; then
    echo "[失败] $f 未链接 docs/ALERT_CODES.md"
    exit 1
  fi
done

echo "[通过] 告警码入口守卫检查完成。"
