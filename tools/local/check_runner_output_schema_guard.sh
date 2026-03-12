#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 runner 输出 schema 文件"
if ! test -f agent_server_new/docs/runner_output.schema.json; then
  echo "[失败] 缺少 agent_server_new/docs/runner_output.schema.json"
  exit 1
fi

echo "[2/2] 运行 runner 输出 schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q agent_server_new/text/test_runner_output_schema.py

echo "[通过] runner 输出 schema 守卫检查完成。"
