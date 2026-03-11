#!/usr/bin/env bash
set -euo pipefail

SCRIPT="scripts/check_contract_docs_index_guard.sh"
SNAPSHOT="docs/contract_docs_index_help_snapshot.txt"

echo "[1/4] 检查守卫脚本与快照文件存在"
if ! test -f "$SCRIPT"; then
  echo "[失败] 缺少 $SCRIPT"
  exit 1
fi
if ! test -f "$SNAPSHOT"; then
  echo "[失败] 缺少 $SNAPSHOT"
  exit 1
fi

echo "[2/4] 提取守卫脚本 --help 输出"
help_output="$(bash "$SCRIPT" --help)"
if [[ -z "$help_output" ]]; then
  echo "[失败] $SCRIPT --help 输出为空"
  exit 1
fi

echo "[3/4] 比对 --help 输出快照"
if ! diff_output="$(diff -u "$SNAPSHOT" <(printf "%s\n" "$help_output") || true)"; then
  :
fi
if [[ -n "$diff_output" ]]; then
  echo "[失败] --help 输出与快照不一致：$SNAPSHOT"
  echo "--- diff (up to 80 lines) ---"
  printf "%s\n" "$diff_output" | sed -n '1,80p'
  exit 1
fi

echo "[4/4] 校验快照包含强约束入口关键项"
for item in "docs/ALERT_CODES.md" "event_center_new/docs/ci_baseline_template.md" "event_center_new/docs/selected_event.schema.json"; do
  if ! rg -q -F "$item" "$SNAPSHOT"; then
    echo "[失败] 快照缺少强约束入口: $item"
    exit 1
  fi
done

echo "[通过] contract docs index help 快照守卫检查完成。"
