#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 execution decision_intent schema 文件"
if ! test -f execution_service/docs/decision_intent.schema.json; then
  echo "[失败] 缺少 execution_service/docs/decision_intent.schema.json"
  exit 1
fi

echo "[2/2] 运行 execution decision_intent schema 校验测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q execution_service/text/test_decision_intent_schema.py

echo "[通过] execution decision_intent schema 守卫检查完成。"
