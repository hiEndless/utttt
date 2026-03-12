#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 runner 输出 schema 文件"
if ! test -f services/agent_server_new/docs/runner_output.schema.json; then
  echo "[失败] 缺少 services/agent_server_new/docs/runner_output.schema.json"
  exit 1
fi

echo "[2/2] 运行 runner 输出 schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/auditors/agent_server_new/test_runner_output_schema.py

echo "[通过] runner 输出 schema 守卫检查完成。"
