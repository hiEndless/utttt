#!/usr/bin/env bash
set -euo pipefail

echo "[1/1] 运行 runtime 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  event_center_new/text/test_main.py \
  event_center_new/text/test_runner.py \
  event_center_new/text/test_runtime_guard_contract.py

echo "[通过] event_center runtime 守卫检查完成。"
