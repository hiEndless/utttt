#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  cat <<'EOF'
用法:
  bash tools/local/check_event_center_runtime_family_guards.sh
  bash tools/local/check_event_center_runtime_family_guards.sh --quick
EOF
  exit 0
fi

if [[ "$MODE" == "--quick" ]]; then
  echo "[1/2] event_center runtime 文档守卫（quick）"
  bash tools/local/check_event_center_runtime_doc_guard.sh

  echo "[2/2] event_center runtime bump tool 守卫（quick）"
  bash tools/local/check_event_center_runtime_bump_tool_guard.sh
  echo "[通过] event_center Runtime 守卫检查完成（quick）。"
  exit 0
fi

if [[ "$MODE" != "all" ]]; then
  echo "[失败] 不支持的参数: $MODE"
  echo "使用 --help 查看可用参数。"
  exit 1
fi

echo "[1/3] event_center runtime 守卫"
bash tools/local/check_event_center_runtime_guard.sh

echo "[2/3] event_center runtime 文档守卫"
bash tools/local/check_event_center_runtime_doc_guard.sh

echo "[3/3] event_center runtime bump tool 守卫"
bash tools/local/check_event_center_runtime_bump_tool_guard.sh

echo "[通过] event_center Runtime 守卫检查完成。"
