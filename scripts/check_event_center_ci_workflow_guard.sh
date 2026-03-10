#!/usr/bin/env bash
set -euo pipefail

QUICK_WF=".github/workflows/event-center-quick.yml"
FULL_WF=".github/workflows/event-center-full.yml"

echo "[1/3] 检查 event_center CI workflow 文件存在"
if ! test -f "$QUICK_WF"; then
  echo "[失败] 缺少 $QUICK_WF"
  exit 1
fi
if ! test -f "$FULL_WF"; then
  echo "[失败] 缺少 $FULL_WF"
  exit 1
fi

echo "[2/3] 校验 quick workflow 失败诊断上传能力"
if ! rg -q "event-center-quick-strict-diagnostics" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 strict 诊断 artifact"
  exit 1
fi
if ! rg -q "event-center-quick-lenient-diagnostics" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 lenient 诊断 artifact"
  exit 1
fi
if ! rg -q "continue-on-error: true" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 continue-on-error 保护"
  exit 1
fi
if ! rg -q "quick strict 失败时终止任务" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 strict 显式失败收敛步骤"
  exit 1
fi
if ! rg -q "quick lenient 失败时终止任务" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 lenient 显式失败收敛步骤"
  exit 1
fi

echo "[3/3] 校验 full workflow 失败诊断上传能力"
if ! rg -q "event-center-full-diagnostics" "$FULL_WF"; then
  echo "[失败] full workflow 缺少全量诊断 artifact"
  exit 1
fi
if ! rg -q "continue-on-error: true" "$FULL_WF"; then
  echo "[失败] full workflow 缺少 continue-on-error 保护"
  exit 1
fi
if ! rg -q "失败时终止任务" "$FULL_WF"; then
  echo "[失败] full workflow 缺少显式失败收敛步骤"
  exit 1
fi

echo "[通过] event_center CI workflow 守卫检查完成。"
