#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution signal_result schema 文件"
if ! test -f execution_service/docs/execution_signal_result.schema.json; then
  echo "[失败] 缺少 execution_service/docs/execution_signal_result.schema.json"
  exit 1
fi

echo "[2/2] 运行 execution signal_result schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q execution_service/text/test_execution_signal_result_schema.py

echo "[通过] execution signal_result schema 守卫检查完成。"
