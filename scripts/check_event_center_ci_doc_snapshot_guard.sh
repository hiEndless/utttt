#!/usr/bin/env bash
set -euo pipefail

DOC="event_center_new/docs/ci.md"
HELP_SNAPSHOT_LINES="event_center_new/docs/ci_help_snapshot_lines.txt"
TRIAGE_SNAPSHOT_LINES="event_center_new/docs/ci_triage_snapshot_lines.txt"

echo "[1/4] 检查 CI 文档与快照关键行文件存在"
if ! test -f "$DOC"; then
  echo "[失败] 缺少 $DOC"
  exit 1
fi
if ! test -f "$HELP_SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $HELP_SNAPSHOT_LINES"
  exit 1
fi
if ! test -f "$TRIAGE_SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $TRIAGE_SNAPSHOT_LINES"
  exit 1
fi

echo "[2/4] 校验快照关键行文件非空且无重复行"
for snapshot in "$HELP_SNAPSHOT_LINES" "$TRIAGE_SNAPSHOT_LINES"; do
  if [[ ! -s "$snapshot" ]]; then
    echo "[失败] 快照关键行文件为空: $snapshot"
    exit 1
  fi
  duplicate_lines="$(sort "$snapshot" | uniq -d || true)"
  if [[ -n "$duplicate_lines" ]]; then
    echo "[失败] 快照关键行文件存在重复行: $snapshot"
    echo "$duplicate_lines"
    exit 1
  fi
  if rg -n -F "　" "$snapshot" >/dev/null; then
    echo "[失败] 快照关键行文件存在全角空格: $snapshot"
    exit 1
  fi
done

if rg -n "[^\\x00-\\x7F]" "$TRIAGE_SNAPSHOT_LINES" >/dev/null; then
  echo "[失败] $TRIAGE_SNAPSHOT_LINES 必须为 ASCII-only（避免排障命令出现不可见字符）"
  exit 1
fi

echo "[3/4] 校验 CI 文档包含帮助快照关键行"
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    continue
  fi
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档缺少帮助快照关键行: $line"
    exit 1
  fi
done < "$HELP_SNAPSHOT_LINES"

echo "[4/4] 校验 CI 文档包含排障命令快照关键行"
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    continue
  fi
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档缺少排障命令快照关键行: $line"
    exit 1
  fi
done < "$TRIAGE_SNAPSHOT_LINES"

echo "[附加检查] 校验帮助快照关键行文件包含 CI 文档守卫失败码"
if ! rg -q -F "EC_GUARD_CI_DOC_FAILED" "$HELP_SNAPSHOT_LINES"; then
  echo "[失败] 快照关键行文件缺少 EC_GUARD_CI_DOC_FAILED"
  exit 1
fi

echo "[通过] event_center CI 文档快照守卫检查完成。"
