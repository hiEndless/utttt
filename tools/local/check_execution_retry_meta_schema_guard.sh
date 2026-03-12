#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution retry_meta schema 文件"
if ! test -f services/execution_service/docs/retry_meta.schema.json; then
  echo "[失败] 缺少 services/execution_service/docs/retry_meta.schema.json"
  exit 1
fi

echo "[2/2] 运行 execution retry_meta schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/execution_service/test_retry_meta_schema.py

echo "[通过] execution retry_meta schema 守卫检查完成。"
