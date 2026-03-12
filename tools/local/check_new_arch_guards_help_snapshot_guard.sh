#!/usr/bin/env bash
set -euo pipefail

SCRIPT="tools/local/check_new_arch_guards.sh"
SNAPSHOT="docs/new_arch_guards_help_snapshot.txt"

echo "[1/4] 检查脚本与快照文件存在"
if ! test -f "$SCRIPT"; then
  echo "[失败] 缺少 $SCRIPT"
  exit 1
fi
if ! test -f "$SNAPSHOT"; then
  echo "[失败] 缺少 $SNAPSHOT"
  exit 1
fi

echo "[2/4] 提取 --help 输出"
help_output="$(bash "$SCRIPT" --help)"
if [[ -z "$help_output" ]]; then
  echo "[失败] $SCRIPT --help 输出为空"
  exit 1
fi

echo "[3/4] 比对 --help 快照"
if ! diff_output="$(diff -u "$SNAPSHOT" <(printf "%s\n" "$help_output") || true)"; then
  :
fi
if [[ -n "$diff_output" ]]; then
  echo "[失败] --help 输出与快照不一致: $SNAPSHOT"
  echo "--- diff (up to 80 lines) ---"
  printf "%s\n" "$diff_output" | sed -n '1,80p'
  exit 1
fi

echo "[4/4] 校验快照关键项"
for item in \
  "--event-center-only" \
  "--event-center-quick" \
  "--strict-wiring/--lenient-wiring" \
  "check_alert_codes_entry_guard.sh" \
  "check_cross_service_time_semantics_doc_guard.sh"; do
  if ! rg -q -F -- "$item" "$SNAPSHOT"; then
    echo "[失败] 快照缺少关键项: $item"
    exit 1
  fi
done

echo "[通过] new_arch_guards help 快照守卫检查完成。"

