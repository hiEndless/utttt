#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 replay summary schema 文件"
if ! test -f services/event_center_new/docs/replay_summary.schema.json; then
  echo "[失败] 缺少 services/event_center_new/docs/replay_summary.schema.json"
  exit 1
fi

echo "[2/2] 运行 replay summary schema 契约测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/replay/event_center_new/test_replay_summary_schema_contract.py

echo "[通过] event_center replay summary schema 守卫检查完成。"
