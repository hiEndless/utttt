#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 检查 event_center replay 入口文件"
if ! test -f event_center_new/replay_main.py; then
  echo "[失败] 缺少 event_center_new/replay_main.py"
  exit 1
fi
if ! test -f event_center_new/ec/pipeline/replay.py; then
  echo "[失败] 缺少 event_center_new/ec/pipeline/replay.py"
  exit 1
fi
if ! test -f event_center_new/ec/pipeline/replay_cli.py; then
  echo "[失败] 缺少 event_center_new/ec/pipeline/replay_cli.py"
  exit 1
fi

echo "[2/3] 运行 event_center replay 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  event_center_new/text/test_runner.py \
  event_center_new/text/test_redis_layer_store.py \
  event_center_new/text/test_replay.py \
  event_center_new/text/test_replay_cli.py

echo "[3/3] 校验 replay CLI 参数"
python3 -m event_center_new.replay_main --help >/dev/null

echo "[通过] event_center replay 守卫检查完成。"
