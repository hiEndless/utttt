#!/usr/bin/env bash
set -euo pipefail

DOC="event_center_new/docs/ci.md"
SNAPSHOT_LINES="event_center_new/docs/ci_help_snapshot_lines.txt"

echo "[1/3] 检查 CI 文档与快照关键行文件存在"
if ! test -f "$DOC"; then
  echo "[失败] 缺少 $DOC"
  exit 1
fi
if ! test -f "$SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $SNAPSHOT_LINES"
  exit 1
fi

echo "[2/3] 校验 CI 文档包含共享快照关键行"
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    continue
  fi
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档帮助快照缺少关键行: $line"
    exit 1
  fi
done < "$SNAPSHOT_LINES"

echo "[3/3] 校验共享快照关键行文件包含 CI 文档守卫失败码"
if ! rg -q -F "EC_GUARD_CI_DOC_FAILED" "$SNAPSHOT_LINES"; then
  echo "[失败] 快照关键行文件缺少 EC_GUARD_CI_DOC_FAILED"
  exit 1
fi

echo "[通过] event_center CI 文档快照守卫检查完成。"
