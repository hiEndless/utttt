#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] 检查告警码文档存在"
if ! test -f docs/ALERT_CODES.md; then
  echo "[失败] 缺少 docs/ALERT_CODES.md"
  exit 1
fi

echo "[2/5] 检查 CONTRACT_INDEX 已收录告警码文档"
if ! rg -q "docs/ALERT_CODES.md" docs/CONTRACT_INDEX.md; then
  echo "[失败] docs/CONTRACT_INDEX.md 未收录 docs/ALERT_CODES.md"
  exit 1
fi

echo "[3/5] 检查三模块 README 已链接告警码文档"
for f in market_state_engine/README.md event_center_new/README.md agent_server_new/README.md; do
  if ! rg -q "docs/ALERT_CODES.md" "$f"; then
    echo "[失败] $f 未链接 docs/ALERT_CODES.md"
    exit 1
  fi
done

echo "[4/5] 检查 ALERT_CODES 表头包含 owner/introduced_in/lifecycle"
if ! rg -q "\| code \| service \| owner \| introduced_in \| lifecycle \| trigger \| signals \|" docs/ALERT_CODES.md; then
  echo "[失败] docs/ALERT_CODES.md 缺少标准表头（owner/introduced_in/lifecycle）"
  exit 1
fi

echo "[5/6] 检查至少存在一条 active 告警码"
if ! rg -q '\| `[^`]+` \| `[^`]+` \| `[^`]+` \| `[^`]+` \| `active` \|' docs/ALERT_CODES.md; then
  echo "[失败] docs/ALERT_CODES.md 未检测到 lifecycle=active 的告警码记录"
  exit 1
fi

echo "[6/6] 检查生命周期规则段落存在"
if ! rg -q "## 生命周期规则" docs/ALERT_CODES.md; then
  echo "[失败] docs/ALERT_CODES.md 缺少生命周期规则段落"
  exit 1
fi
if ! rg -q "active -> deprecated -> removed" docs/ALERT_CODES.md; then
  echo "[失败] docs/ALERT_CODES.md 缺少生命周期状态转换规则"
  exit 1
fi

echo "[通过] 告警码入口守卫检查完成。"
