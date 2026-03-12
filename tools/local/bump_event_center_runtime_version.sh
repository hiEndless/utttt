#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DOC="event_center_new/docs/runtime.md"
MAIN_FILE="services/event_center_new/runtime/main.py"

usage() {
  cat <<'EOF'
用法:
  bash tools/local/bump_event_center_runtime_version.sh --print-current-version
  bash tools/local/bump_event_center_runtime_version.sh <version> <note>
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --date YYYY-MM-DD
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --dry-run
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --check-clean
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --apply-from-env-table
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --no-duplicate-log
  bash tools/local/bump_event_center_runtime_version.sh <version> <note> --strict
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--print-current-version" ]]; then
  if ! test -f "$RUNTIME_DOC"; then
    echo "[失败] 缺少文档: $RUNTIME_DOC"
    exit 1
  fi
  current_version="$(rg -o 'runtime_config_version:\s*[A-Za-z0-9._-]+' "$RUNTIME_DOC" | head -n1 | sed -E 's/.*runtime_config_version:\s*//' | xargs)"
  if [[ -z "$current_version" ]]; then
    echo "[失败] 未在 $RUNTIME_DOC 中找到 runtime_config_version"
    exit 1
  fi
  echo "$current_version"
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
dry_run="false"
check_clean="false"
apply_from_env_table="false"
no_duplicate_log="false"
strict_mode="false"
shift 2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      date_override="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    --check-clean)
      check_clean="true"
      shift
      ;;
    --apply-from-env-table)
      apply_from_env_table="true"
      shift
      ;;
    --no-duplicate-log)
      no_duplicate_log="true"
      shift
      ;;
    --strict)
      strict_mode="true"
      shift
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$strict_mode" == "true" ]]; then
  check_clean="true"
  apply_from_env_table="true"
  no_duplicate_log="true"
fi

if ! [[ "$version" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "[失败] version 格式非法: $version"
  exit 1
fi

if ! test -f "$RUNTIME_DOC"; then
  echo "[失败] 缺少文档: $RUNTIME_DOC"
  exit 1
fi
if ! test -f "$MAIN_FILE"; then
  echo "[失败] 缺少入口文件: $MAIN_FILE"
  exit 1
fi

if [[ "$check_clean" == "true" ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[失败] 工作区不干净，拒绝升级版本（可移除 --check-clean 或先提交变更）。"
    exit 1
  fi
fi

if [[ "$apply_from_env_table" == "true" ]]; then
  keys_raw="$(rg -o 'EVENT_CENTER_[A-Z0-9_]+' "$MAIN_FILE" | sort -u || true)"
  if [[ -z "$keys_raw" ]]; then
    echo "[失败] 未从 $MAIN_FILE 提取到 EVENT_CENTER_ 环境变量。"
    exit 1
  fi
  while IFS= read -r key; do
    if [[ -z "$key" ]]; then
      continue
    fi
    if ! rg -q "$key" "$RUNTIME_DOC"; then
      echo "[失败] runtime 文档缺少环境变量: $key"
      echo "提示：先更新 $RUNTIME_DOC 再执行 bump。"
      exit 1
    fi
  done <<< "$keys_raw"
fi

if [[ "$no_duplicate_log" == "true" ]]; then
  latest_log_version="$(rg -o 'version:\s*`[A-Za-z0-9._-]+`' "$RUNTIME_DOC" | head -n1 | sed -E 's/.*`([^`]+)`.*/\1/')"
  if [[ -n "$latest_log_version" && "$latest_log_version" == "$version" ]]; then
    echo "[失败] 变更日志最新条目已是同版本: ${version} (可移除 --no-duplicate-log 允许重复记录)。"
    exit 1
  fi
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

if [[ "$dry_run" == "true" ]]; then
  echo "[预览] dry-run 模式，不写入文件。"
  echo "target_file=$RUNTIME_DOC"
  echo "version=$version"
  echo "date=$target_date"
  echo "entry=$entry"
  exit 0
fi

mv "$tmp2" "$RUNTIME_DOC"
echo "[通过] 已更新 $RUNTIME_DOC"
echo "version=$version"
echo "date=$target_date"
