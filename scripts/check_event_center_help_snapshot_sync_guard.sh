#!/usr/bin/env bash
set -euo pipefail

GUARD_SCRIPT="scripts/check_event_center_contract_guards.sh"
SNAPSHOT_LINES="event_center_new/docs/ci_help_snapshot_lines.txt"
SNAPSHOT_BLOCK="event_center_new/docs/ci_help_block_snapshot.txt"

echo "[1/7] 检查脚本与快照文件存在"
if ! test -f "$GUARD_SCRIPT"; then
  echo "[失败] 缺少 $GUARD_SCRIPT"
  exit 1
fi
if ! test -f "$SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $SNAPSHOT_LINES"
  exit 1
fi
if ! test -f "$SNAPSHOT_BLOCK"; then
  echo "[失败] 缺少 $SNAPSHOT_BLOCK"
  exit 1
fi

echo "[2/7] 提取守卫脚本 --help 完整输出"
help_output="$(bash "$GUARD_SCRIPT" --help)"
if [[ -z "$help_output" ]]; then
  echo "[失败] --help 输出为空"
  exit 1
fi

echo "[3/7] 比对 --help 完整快照块"
if ! diff -u "$SNAPSHOT_BLOCK" <(printf "%s\n" "$help_output") >/dev/null; then
  echo "[失败] --help 完整输出与快照不一致: $SNAPSHOT_BLOCK"
  echo "可执行：bash scripts/check_event_center_contract_guards.sh --help"
  exit 1
fi

echo "[4/7] 提取守卫脚本 --help 的失败码（保序）"
help_codes="$(printf "%s\n" "$help_output" | rg -o "EC_GUARD_[A-Z_]+" || true)"
if [[ -z "$help_codes" ]]; then
  echo "[失败] 未从 --help 提取到失败码（保序）"
  exit 1
fi

echo "[5/7] 提取快照关键行文件中的失败码（保序）"
snapshot_codes="$(rg -o "EC_GUARD_[A-Z_]+" "$SNAPSHOT_LINES" || true)"
if [[ -z "$snapshot_codes" ]]; then
  echo "[失败] 未从快照关键行文件提取到失败码（保序）"
  exit 1
fi

echo "[6/7] 比对失败码数量一致性"
help_count="$(echo "$help_codes" | wc -l | tr -d ' ')"
snapshot_count="$(echo "$snapshot_codes" | wc -l | tr -d ' ')"
if [[ "$help_count" != "$snapshot_count" ]]; then
  echo "[失败] --help 与快照关键行文件失败码数量不一致"
  echo "help_count=$help_count snapshot_count=$snapshot_count"
  exit 1
fi

echo "[7/7] 比对失败码顺序一致性"
if [[ "$help_codes" != "$snapshot_codes" ]]; then
  echo "[失败] --help 与快照关键行文件失败码顺序不一致"
  echo "--- help codes ---"
  echo "$help_codes"
  echo "--- snapshot codes ---"
  echo "$snapshot_codes"
  exit 1
fi

echo "[通过] event_center 帮助快照同步守卫检查完成。"
