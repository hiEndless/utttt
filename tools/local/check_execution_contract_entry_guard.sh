#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] 检查 CONTRACT_INDEX 存在且包含更新时间"
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少 docs/CONTRACT_INDEX.md"
  exit 1
fi
if ! rg -n "更新时间：" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 缺少更新时间字段"
  exit 1
fi

echo "[2/4] 读取 execution schema mapping 版本常量"
expected="$(./venv/bin/python - <<'PY'
from execution_service.version import SCHEMA_MAPPING_VERSION
print(SCHEMA_MAPPING_VERSION)
PY
)"

echo "[3/4] 校验 CONTRACT_INDEX execution 版本声明与代码一致"
if ! rg -n "execution_schema_mapping_version:\s*${expected}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 execution_schema_mapping_version=${expected}"
  exit 1
fi

echo "[4/4] 校验 schema_mapping.last_updated 必须等于 CONTRACT_INDEX 更新时间"
./venv/bin/python - <<'PY'
import json
import re
from datetime import date
from pathlib import Path

contract_index = Path("docs/CONTRACT_INDEX.md").read_text(encoding="utf-8")
match = re.search(r"更新时间：\s*(\d{4}-\d{2}-\d{2})", contract_index)
if not match:
    raise SystemExit("[失败] CONTRACT_INDEX 更新时间格式不正确")
index_day = date.fromisoformat(match.group(1))

mapping = json.loads(Path("services/execution_service/docs/schema_mapping.json").read_text(encoding="utf-8"))
mapping_day = date.fromisoformat(str(mapping.get("last_updated") or "").strip())

if mapping_day != index_day:
    raise SystemExit(
        f"[失败] schema_mapping.last_updated={mapping_day.isoformat()} 必须等于 CONTRACT_INDEX 更新时间={index_day.isoformat()}"
    )
PY

echo "[通过] execution 合同入口守卫检查完成。"
