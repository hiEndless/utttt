#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DOC="event_center_new/docs/runtime.md"
MAIN_FILE="services/event_center_new/runtime/main.py"
SHOW_SETS="false"

if [[ "${1:-}" == "--show-sets" ]]; then
  SHOW_SETS="true"
elif [[ -n "${1:-}" ]]; then
  echo "[失败] 不支持的参数: $1"
  echo "用法: bash scripts/check_event_center_runtime_doc_guard.sh [--show-sets]"
  exit 1
fi

echo "[1/3] 检查 runtime 文档与入口文件存在"
if ! test -f "$RUNTIME_DOC"; then
  echo "[失败] 缺少 $RUNTIME_DOC"
  exit 1
fi
if ! test -f "$MAIN_FILE"; then
  echo "[失败] 缺少 $MAIN_FILE"
  exit 1
fi

echo "[2/3] 校验 main.py 与 runtime.md 的 EVENT_CENTER_* 变量集合一致"
tmp_main="$(mktemp)"
tmp_doc="$(mktemp)"
tmp_main_only="$(mktemp)"
tmp_doc_only="$(mktemp)"
trap 'rm -f "$tmp_main" "$tmp_doc" "$tmp_main_only" "$tmp_doc_only"' EXIT

rg -o 'EVENT_CENTER_[A-Z0-9_]+' "$MAIN_FILE" | sort -u > "$tmp_main"
rg -o 'EVENT_CENTER_[A-Z0-9_]+' "$RUNTIME_DOC" | sort -u > "$tmp_doc"

if [[ "$SHOW_SETS" == "true" ]]; then
  echo "[调试] main.py 变量集合："
  cat "$tmp_main"
  echo "[调试] runtime.md 变量集合："
  cat "$tmp_doc"
fi

if ! test -s "$tmp_main"; then
  echo "[失败] 未从 main.py 提取到 EVENT_CENTER_* 变量"
  exit 1
fi
if ! test -s "$tmp_doc"; then
  echo "[失败] 未从 runtime.md 提取到 EVENT_CENTER_* 变量"
  exit 1
fi

comm -23 "$tmp_main" "$tmp_doc" > "$tmp_main_only"
comm -13 "$tmp_main" "$tmp_doc" > "$tmp_doc_only"

if test -s "$tmp_main_only"; then
  echo "[失败] 以下变量存在于 main.py 但不在 runtime.md："
  cat "$tmp_main_only"
  exit 1
fi
if test -s "$tmp_doc_only"; then
  echo "[失败] 以下变量存在于 runtime.md 但不在 main.py："
  cat "$tmp_doc_only"
  exit 1
fi

echo "[3/3] 校验 runtime 文档版本与变更日志最新条目一致"
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
