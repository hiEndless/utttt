#!/usr/bin/env bash
set -euo pipefail

QUICK_WF=".github/workflows/event-center-quick.yml"
FULL_WF=".github/workflows/event-center-full.yml"
SETUP_ACTION=".github/actions/setup-utaker-python/action.yml"
QUICK_STRICT_ENTRY="tools/ci/event_center_quick_strict.sh"
QUICK_LENIENT_ENTRY="tools/ci/event_center_quick_lenient.sh"
FULL_STRICT_ENTRY="tools/ci/event_center_full_strict.sh"
CI_META_SCRIPT="tools/ci/event_center_emit_meta_header.sh"

echo "[1/4] 检查 event_center CI workflow、复用 action 与 CI 元信息脚本存在"
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
if ! test -f "$CI_META_SCRIPT"; then
  echo "[失败] 缺少 $CI_META_SCRIPT"
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
if ! rg -q "$QUICK_STRICT_ENTRY" "$QUICK_WF"; then
  echo "[失败] quick workflow 未通过 tools/ci quick strict 入口执行守卫"
  exit 1
fi
if ! rg -q "$QUICK_LENIENT_ENTRY" "$QUICK_WF"; then
  echo "[失败] quick workflow 未通过 tools/ci quick lenient 入口执行守卫"
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
if ! rg -q -F "pwd && ls -la ." "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少最短排障命令串提示（pwd/ls）"
  exit 1
fi
if ! rg -q -F "quick_strict.log quick_lenient.log" "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少最短排障命令串提示"
  exit 1
fi
if ! rg -q 'rg -n .*CI_GUARD.*quick_strict\.log quick_lenient\.log' "$QUICK_WF"; then
  echo "[失败] quick workflow 缺少 CI_GUARD 摘要排障命令"
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
if ! rg -q "$FULL_STRICT_ENTRY" "$FULL_WF"; then
  echo "[失败] full workflow 未通过 tools/ci full strict 入口执行守卫"
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
if ! rg -q -F "pwd && ls -la ." "$FULL_WF"; then
  echo "[失败] full workflow 缺少最短排障命令串提示（pwd/ls）"
  exit 1
fi
if ! rg -q -F "full_guard.log" "$FULL_WF"; then
  echo "[失败] full workflow 缺少最短排障命令串提示"
  exit 1
fi
if ! rg -q 'rg -n .*CI_GUARD.*full_guard\.log' "$FULL_WF"; then
  echo "[失败] full workflow 缺少 CI_GUARD 摘要排障命令"
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
if ! rg -q "runtime_config_version" "$CI_META_SCRIPT"; then
  echo "[失败] CI 元信息脚本缺少 runtime_config_version 输出"
  exit 1
fi

echo "[通过] event_center CI workflow 守卫检查完成。"
