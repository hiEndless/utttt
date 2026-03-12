#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution decision_state schema 文件"
if ! test -f services/execution_service/docs/decision_state.schema.json; then
  echo "[失败] 缺少 services/execution_service/docs/decision_state.schema.json"
  exit 1
fi

echo "[2/2] 运行 execution decision_state schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/execution_service/test_decision_state_schema.py

echo "[通过] execution decision_state schema 守卫检查完成。"
