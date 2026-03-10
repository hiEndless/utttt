#!/usr/bin/env bash
set -euo pipefail

GUARD_SCRIPT="scripts/check_event_center_contract_guards.sh"
SNAPSHOT_LINES="event_center_new/docs/ci_help_snapshot_lines.txt"

echo "[1/4] 检查脚本与快照关键行文件存在"
if ! test -f "$GUARD_SCRIPT"; then
  echo "[失败] 缺少 $GUARD_SCRIPT"
  exit 1
fi
if ! test -f "$SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $SNAPSHOT_LINES"
  exit 1
fi

echo "[2/5] 提取守卫脚本 --help 的失败码（保序）"
help_codes="$(bash "$GUARD_SCRIPT" --help | rg -o "EC_GUARD_[A-Z_]+" || true)"
if [[ -z "$help_codes" ]]; then
  echo "[失败] 未从 --help 提取到失败码（保序）"
  exit 1
fi

echo "[3/5] 提取快照关键行文件中的失败码（保序）"
snapshot_codes="$(rg -o "EC_GUARD_[A-Z_]+" "$SNAPSHOT_LINES" || true)"
if [[ -z "$snapshot_codes" ]]; then
  echo "[失败] 未从快照关键行文件提取到失败码（保序）"
  exit 1
fi

echo "[4/5] 比对失败码数量一致性"
help_count="$(echo "$help_codes" | wc -l | tr -d ' ')"
snapshot_count="$(echo "$snapshot_codes" | wc -l | tr -d ' ')"
if [[ "$help_count" != "$snapshot_count" ]]; then
  echo "[失败] --help 与快照关键行文件失败码数量不一致"
  echo "help_count=$help_count snapshot_count=$snapshot_count"
  exit 1
fi

echo "[5/5] 比对失败码顺序一致性"
if [[ "$help_codes" != "$snapshot_codes" ]]; then
  echo "[失败] --help 与快照关键行文件失败码顺序不一致"
  echo "--- help codes ---"
  echo "$help_codes"
  echo "--- snapshot codes ---"
  echo "$snapshot_codes"
  exit 1
fi

echo "[通过] event_center 帮助快照同步守卫检查完成。"
