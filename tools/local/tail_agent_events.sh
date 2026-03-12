#!/usr/bin/env bash
set -euo pipefail

DEFAULT_PATH="verification/reports/agent_server_new_events.jsonl"
FILE_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-$DEFAULT_PATH}"
LINES="${TAIL_LINES:-100}"

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
用法:
  bash tools/local/tail_agent_events.sh [file_path] [tail_args...]

说明:
  默认读取 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl。
  若开启按日滚动，会优先选择同名前缀下最新文件。
  默认 tail 行数来自 TAIL_LINES（默认 100）。
EOF
  exit 0
fi

if [[ $# -gt 0 && "${1:-}" != -* ]]; then
  FILE_PATH="$1"
  shift
fi

DIR="$(dirname "$FILE_PATH")"
BASE="$(basename "$FILE_PATH")"
NAME="${BASE%.*}"
EXT="${BASE##*.}"

LATEST="$FILE_PATH"
if [[ -d "$DIR" ]]; then
  CANDIDATE="$(ls -1t "$DIR"/"$NAME"*".$EXT" 2>/dev/null | head -n 1 || true)"
  if [[ -n "$CANDIDATE" ]]; then
    LATEST="$CANDIDATE"
  fi
fi

if [[ ! -f "$LATEST" ]]; then
  echo "[失败] 未找到日志文件: $LATEST"
  exit 1
fi

if [[ $# -eq 0 ]]; then
  exec tail -n "$LINES" -f "$LATEST"
fi

exec tail "$@" "$LATEST"

