#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution schema mapping 清单文件"
if ! test -f services/execution_service/docs/schema_mapping.json; then
  echo "[失败] 缺少 services/execution_service/docs/schema_mapping.json"
  exit 1
fi

echo "[2/2] 运行 execution schema mapping 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/execution_service/test_schema_mapping.py

echo "[通过] execution schema mapping 守卫检查完成。"
