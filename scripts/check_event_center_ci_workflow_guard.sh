#!/usr/bin/env bash
set -euo pipefail

QUICK_WF=".github/workflows/event-center-quick.yml"
FULL_WF=".github/workflows/event-center-full.yml"
SETUP_ACTION=".github/actions/setup-utaker-python/action.yml"

echo "[1/4] 检查 event_center CI workflow 与复用 action 文件存在"
if ! test -f "$QUICK_WF"; then
  echo "[失败] 缺少 $QUICK_WF"
  exit 1
fi
if ! test -f "$FULL_WF"; then
  echo "[失败] 缺少 $FULL_WF"
  exit 1
fi
if ! test -f "$SETUP_ACTION"; then
  echo "[失败] 缺少 $SETUP_ACTION"
  exit 1
fi

echo "[2/4] 校验 quick workflow 失败诊断上传能力与复用 action"
if ! rg -q "uses: \\.\\/\\.github\\/actions\\/setup-utaker-python" "$QUICK_WF"; then
  echo "[失败] quick workflow 未复用 setup-utaker-python action"
  exit 1
fi
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

echo "[3/4] 校验 full workflow 失败诊断上传能力与复用 action"
if ! rg -q "uses: \\.\\/\\.github\\/actions\\/setup-utaker-python" "$FULL_WF"; then
  echo "[失败] full workflow 未复用 setup-utaker-python action"
  exit 1
fi
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

echo "[4/4] 校验 setup-utaker-python action 依赖安装行为"
if ! rg -q "actions/setup-python@v5" "$SETUP_ACTION"; then
  echo "[失败] setup action 缺少 actions/setup-python@v5"
  exit 1
fi
if ! rg -q "pip install -r" "$SETUP_ACTION"; then
  echo "[失败] setup action 缺少 requirements 安装步骤"
  exit 1
fi

echo "[通过] event_center CI workflow 守卫检查完成。"
