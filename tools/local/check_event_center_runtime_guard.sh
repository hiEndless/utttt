#!/usr/bin/env bash
set -euo pipefail

echo "[1/1] 运行 runtime 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  verification/replay/event_center_new/test_main.py \
  verification/replay/event_center_new/test_runner.py \
  verification/replay/event_center_new/test_runtime_guard_contract.py

echo "[通过] event_center runtime 守卫检查完成。"
