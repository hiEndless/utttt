#!/usr/bin/env bash
set -euo pipefail

SCRIPT="tools/local/check_market_state_engine_guard.sh"
SNAPSHOT="services/market_state_engine/docs/guard_help_snapshot.txt"

echo "[1/3] 检查状态层守卫脚本与快照文件存在"
if ! test -f "$SCRIPT"; then
  echo "[失败] 缺少 $SCRIPT"
  exit 1
fi
if ! test -f "$SNAPSHOT"; then
  echo "[失败] 缺少 $SNAPSHOT"
  exit 1
fi

echo "[2/3] 提取状态层守卫脚本 --help 输出"
help_output="$(bash "$SCRIPT" --help)"
if [[ -z "$help_output" ]]; then
  echo "[失败] $SCRIPT --help 输出为空"
  exit 1
fi

echo "[3/3] 比对状态层守卫 --help 快照"
if ! diff_output="$(diff -u "$SNAPSHOT" <(printf "%s\n" "$help_output") || true)"; then
  :
fi
if [[ -n "$diff_output" ]]; then
  echo "[失败] 状态层守卫 --help 输出与快照不一致: $SNAPSHOT"
  echo "--- diff (up to 80 lines) ---"
  printf "%s\n" "$diff_output" | sed -n '1,80p'
  exit 1
fi

echo "[通过] market_state_engine help 快照守卫检查完成。"
