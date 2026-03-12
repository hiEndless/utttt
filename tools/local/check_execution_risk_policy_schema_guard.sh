#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution risk_policy schema 文件"
if ! test -f execution_service/docs/risk_policy.schema.json; then
  echo "[失败] 缺少 execution_service/docs/risk_policy.schema.json"
  exit 1
fi

echo "[2/2] 运行 execution risk_policy schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/execution_service/test_risk_policy_schema.py

echo "[通过] execution risk_policy schema 守卫检查完成。"
