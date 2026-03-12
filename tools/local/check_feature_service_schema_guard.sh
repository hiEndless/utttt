#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) 冻结 schema 文件必须存在
# 2) feature_service schema 守卫测试必须通过

RAW_SCHEMA="services/feature_service/docs/schemas/raw_structure_response.schema.json"
FEATURE_SCHEMA="services/feature_service/docs/schemas/feature_response.schema.json"

echo "[1/2] 检查冻结 schema 文件"
test -f "${RAW_SCHEMA}" || { echo "[失败] 缺少 ${RAW_SCHEMA}"; exit 1; }
test -f "${FEATURE_SCHEMA}" || { echo "[失败] 缺少 ${FEATURE_SCHEMA}"; exit 1; }

echo "[2/2] 运行 schema 守卫测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  verification/validators/feature_service/test_feature_service_schema_guard.py \
  verification/validators/feature_service/test_feature_service_routes_contract.py

echo "[通过] feature_service schema 守卫检查完成。"
