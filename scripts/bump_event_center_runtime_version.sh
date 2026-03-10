#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DOC="event_center_new/docs/runtime.md"

usage() {
  cat <<'EOF'
用法:
  bash scripts/bump_event_center_runtime_version.sh <version> <note>
  bash scripts/bump_event_center_runtime_version.sh <version> <note> --date YYYY-MM-DD

示例:
  bash scripts/bump_event_center_runtime_version.sh event-center-runtime-v2 "新增 EVENT_CENTER_FOO"
  bash scripts/bump_event_center_runtime_version.sh event-center-runtime-v2 "新增 EVENT_CENTER_FOO" --date 2026-03-11
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  echo "[失败] 参数不足。"
  usage
  exit 1
fi

version="$1"
note="$2"
date_override=""
shift 2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      date_override="${2:-}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      usage
      exit 1
      ;;
  esac
done

if ! [[ "$version" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "[失败] version 格式非法: $version"
  exit 1
fi

if ! test -f "$RUNTIME_DOC"; then
  echo "[失败] 缺少文档: $RUNTIME_DOC"
  exit 1
fi

today="$(date +%F)"
target_date="${date_override:-$today}"
entry="- version: \`$version\` | date: \`$target_date\` | note: $note"

tmp1="$(mktemp)"
tmp2="$(mktemp)"
trap 'rm -f "$tmp1" "$tmp2"' EXIT

awk -v ver="$version" '
BEGIN { updated=0 }
{
  if ($0 ~ /^- `runtime_config_version:/) {
    print "- `runtime_config_version: " ver "`"
    updated=1
    next
  }
  print $0
}
END {
  if (updated == 0) exit 2
}
' "$RUNTIME_DOC" > "$tmp1" || {
  echo "[失败] 未找到 runtime_config_version 行。"
  exit 1
}

awk -v entry="$entry" '
BEGIN { inserted=0 }
{
  print $0
  if (inserted == 0 && $0 ~ /^### 0\.1 变更日志（新到旧）$/) {
    print ""
    print entry
    inserted=1
  }
}
END {
  if (inserted == 0) exit 2
}
' "$tmp1" > "$tmp2" || {
  echo "[失败] 未找到变更日志标题。"
  exit 1
}

mv "$tmp2" "$RUNTIME_DOC"
echo "[通过] 已更新 $RUNTIME_DOC"
echo "version=$version"
echo "date=$target_date"
