#!/usr/bin/env bash
set -euo pipefail

# 守卫目标：
# 1) market_state_engine 不得恢复 feature 旧契约回退逻辑
# 2) feature 版本常量/manifest/CONTRACT_INDEX 必须一致
# 3) feature 新契约行为测试必须通过

TARGET_FILE="services/market_state_engine/src/adapters/raw_structure_http.py"

echo "[1/3] 检查是否出现旧契约回退代码"
if rg -n 'data\.get\("raw_market_structure"\)' "${TARGET_FILE}" | rg -v 'data_block\.get\("raw_market_structure"\)'; then
  echo "[失败] 检测到顶层 raw_market_structure 回退解析，请移除。"
  exit 1
fi

if rg -n 'return dict\(data\.get\("data"\)' "${TARGET_FILE}"; then
  echo "[失败] 检测到 data 兜底回退解析，请移除。"
  exit 1
fi

echo "[2/3] 校验 feature 版本声明一致性"
expected_feature_version="$(./venv/bin/python - <<'PY'
from services.feature_service.src.version import FEATURE_RESPONSE_SCHEMA_VERSION
print(FEATURE_RESPONSE_SCHEMA_VERSION)
PY
)"
if ! rg -n "feature_response_schema_version:\s*${expected_feature_version}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 feature_response_schema_version=${expected_feature_version}"
  exit 1
fi
./venv/bin/python - <<'PY'
import re
from pathlib import Path
from services.feature_service.src.version import FEATURE_RESPONSE_SCHEMA_VERSION

text = Path("contracts/versions/manifest.yaml").read_text(encoding="utf-8")
m = re.search(r"- name:\s*feature_response_schema_version\s*\n\s*value:\s*\"([^\"]+)\"", text, re.MULTILINE)
if not m:
    raise SystemExit("[失败] manifest 缺少 feature_response_schema_version")
if str(m.group(1)) != str(FEATURE_RESPONSE_SCHEMA_VERSION):
    raise SystemExit(
        f"[失败] manifest feature_response_schema_version 与代码不一致: {m.group(1)} != {FEATURE_RESPONSE_SCHEMA_VERSION}"
    )
PY

echo "[3/3] 运行契约守卫测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q verification/validators/feature_service/test_feature_service_routes_contract.py

echo "[通过] feature 契约守卫检查完成。"
