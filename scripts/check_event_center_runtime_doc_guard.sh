#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DOC="event_center_new/docs/runtime.md"
MAIN_FILE="event_center_new/main.py"

echo "[1/4] 检查 runtime 文档与入口文件存在"
if ! test -f "$RUNTIME_DOC"; then
  echo "[失败] 缺少 $RUNTIME_DOC"
  exit 1
fi
if ! test -f "$MAIN_FILE"; then
  echo "[失败] 缺少 $MAIN_FILE"
  exit 1
fi

echo "[2/4] 校验关键环境变量在 main.py 中存在"
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

echo "[3/4] 校验关键环境变量在 runtime.md 中存在"
for key in "${keys[@]}"; do
  if ! rg -q "$key" "$RUNTIME_DOC"; then
    echo "[失败] runtime.md 缺少环境变量: $key"
    exit 1
  fi
done

echo "[4/4] 校验 runtime 文档版本与变更日志最新条目一致"
doc_version="$(rg -o 'runtime_config_version:\s*[A-Za-z0-9._-]+' "$RUNTIME_DOC" | head -n1 | sed -E 's/.*runtime_config_version:\s*//' | xargs)"
latest_log_version="$(rg -o 'version:\s*`[A-Za-z0-9._-]+`' "$RUNTIME_DOC" | head -n1 | sed -E 's/.*`([^`]+)`.*/\1/')"
if [[ -z "$doc_version" ]]; then
  echo "[失败] runtime.md 缺少 runtime_config_version"
  exit 1
fi
if [[ -z "$latest_log_version" ]]; then
  echo "[失败] runtime.md 缺少变更日志 version 条目"
  exit 1
fi
if [[ "$doc_version" != "$latest_log_version" ]]; then
  echo "[失败] runtime 版本不一致 doc=$doc_version latest_log=$latest_log_version"
  exit 1
fi

echo "[通过] event_center runtime 文档守卫检查完成。"
