#!/usr/bin/env bash
set -euo pipefail

DEFAULT_PATH="verification/reports/agent_server_new_events.jsonl"
FILE_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-$DEFAULT_PATH}"
LINES="${TAIL_LINES:-100}"
EVENT_ID_FILTER=""
AGENT_NAME_FILTER=""
RECORD_TYPE_FILTER=""
CONTAINS_FILTER=""
FOLLOW_MODE=1

print_help() {
  cat <<'EOF'
用法:
  bash tools/local/tail_agent_events.sh [file_path] [options]

选项:
  --event-id <id>         仅显示指定 event_id
  --agent-name <name>     仅显示指定 agent_name（仅 record_type=agent_output 有效）
  --record-type <type>    仅显示指定 record_type（market_context|agent_output）
  --contains <keyword>    仅显示包含关键字的 JSON 行（子串匹配）
  --lines <n>             tail 行数（默认读取 TAIL_LINES 或 100）
  --no-follow             只输出当前内容，不持续跟踪
  --help                  显示帮助

说明:
  默认读取 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl。
  若开启按日滚动，会优先选择同名前缀下最新文件。
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  print_help
  exit 0
fi

if [[ $# -gt 0 && "${1:-}" != -* ]]; then
  FILE_PATH="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "${1:-}" in
    --event-id)
      EVENT_ID_FILTER="${2:-}"
      shift 2
      ;;
    --agent-name)
      AGENT_NAME_FILTER="${2:-}"
      shift 2
      ;;
    --record-type)
      RECORD_TYPE_FILTER="${2:-}"
      shift 2
      ;;
    --contains)
      CONTAINS_FILTER="${2:-}"
      shift 2
      ;;
    --lines)
      LINES="${2:-100}"
      shift 2
      ;;
    --no-follow)
      FOLLOW_MODE=0
      shift
      ;;
    --help)
      print_help
      exit 0
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      print_help
      exit 1
      ;;
  esac
done

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

TAIL_ARGS=(-n "$LINES")
if [[ "$FOLLOW_MODE" == "1" ]]; then
  TAIL_ARGS+=(-f)
fi

if [[ -z "$EVENT_ID_FILTER" && -z "$AGENT_NAME_FILTER" && -z "$RECORD_TYPE_FILTER" && -z "$CONTAINS_FILTER" ]]; then
  exec tail "${TAIL_ARGS[@]}" "$LATEST"
fi

tail "${TAIL_ARGS[@]}" "$LATEST" | EVENT_ID_FILTER="$EVENT_ID_FILTER" AGENT_NAME_FILTER="$AGENT_NAME_FILTER" RECORD_TYPE_FILTER="$RECORD_TYPE_FILTER" CONTAINS_FILTER="$CONTAINS_FILTER" \
python3 -c '
import json
import os
import sys

event_id = (os.getenv("EVENT_ID_FILTER") or "").strip()
agent_name = (os.getenv("AGENT_NAME_FILTER") or "").strip()
record_type = (os.getenv("RECORD_TYPE_FILTER") or "").strip()
contains = (os.getenv("CONTAINS_FILTER") or "").strip()

for line in sys.stdin:
    raw = line.rstrip("\n")
    if not raw:
        continue
    if contains and contains not in raw:
        continue
    try:
        obj = json.loads(raw)
    except Exception:
        continue
    if event_id and str(obj.get("event_id") or "") != event_id:
        continue
    if agent_name and str(obj.get("agent_name") or "") != agent_name:
        continue
    if record_type and str(obj.get("record_type") or "") != record_type:
        continue
    print(raw, flush=True)
'
