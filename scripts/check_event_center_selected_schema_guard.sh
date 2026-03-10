#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 selected_event schema 文件"
if ! test -f event_center_new/docs/selected_event.schema.json; then
  echo "[失败] 缺少 event_center_new/docs/selected_event.schema.json"
  exit 1
fi

echo "[2/2] 运行 selected_event schema 契约测试（含缺必填字段行为断言）"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q event_center_new/text/test_selected_event_schema_contract.py

echo "[通过] event_center selected_event schema 守卫检查完成。"
