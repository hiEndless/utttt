#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DOC="event_center_new/docs/runtime.md"
MAIN_FILE="event_center_new/main.py"

echo "[1/3] 检查 runtime 文档与入口文件存在"
if ! test -f "$RUNTIME_DOC"; then
  echo "[失败] 缺少 $RUNTIME_DOC"
  exit 1
fi
if ! test -f "$MAIN_FILE"; then
  echo "[失败] 缺少 $MAIN_FILE"
  exit 1
fi

echo "[2/3] 校验关键环境变量在 main.py 中存在"
keys=(
  EVENT_CENTER_LAYER_STORE_MODE
  EVENT_CENTER_REDIS_URL
  EVENT_CENTER_STREAM_RAW
  EVENT_CENTER_STREAM_NORMALIZED
  EVENT_CENTER_STREAM_EVIDENCE
  EVENT_CENTER_STREAM_CONTEXT
  EVENT_CENTER_STREAM_SELECTED
  EVENT_CENTER_STREAM_MAXLEN
  EVENT_CENTER_STREAM_APPROX
  EVENT_CENTER_RUN_LOOP
  EVENT_CENTER_RUN_INTERVAL_MS
  EVENT_CENTER_RUN_MAX_TICKS
  EVENT_CENTER_STOP_ON_ERROR
  EVENT_CENTER_HEALTH_KEY
  EVENT_CENTER_SELF_CHECK_ONLY
)
for key in "${keys[@]}"; do
  if ! rg -q "$key" "$MAIN_FILE"; then
    echo "[失败] main.py 缺少环境变量: $key"
    exit 1
  fi
done

echo "[3/3] 校验关键环境变量在 runtime.md 中存在"
for key in "${keys[@]}"; do
  if ! rg -q "$key" "$RUNTIME_DOC"; then
    echo "[失败] runtime.md 缺少环境变量: $key"
    exit 1
  fi
done

echo "[通过] event_center runtime 文档守卫检查完成。"
