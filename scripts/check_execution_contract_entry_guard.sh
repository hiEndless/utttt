#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 检查 CONTRACT_INDEX 存在且包含更新时间"
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少 docs/CONTRACT_INDEX.md"
  exit 1
fi
if ! rg -n "更新时间：" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 缺少更新时间字段"
  exit 1
fi

echo "[2/3] 读取 execution schema mapping 版本常量"
expected="$(./venv/bin/python - <<'PY'
from execution_service.version import SCHEMA_MAPPING_VERSION
print(SCHEMA_MAPPING_VERSION)
PY
)"

echo "[3/3] 校验 CONTRACT_INDEX execution 版本声明与代码一致"
if ! rg -n "execution_schema_mapping_version:\s*${expected}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 execution_schema_mapping_version=${expected}"
  exit 1
fi

echo "[通过] execution 合同入口守卫检查完成。"
