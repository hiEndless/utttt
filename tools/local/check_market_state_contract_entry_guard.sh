#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] 检查 CONTRACT_INDEX 存在且包含更新时间"
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少 docs/CONTRACT_INDEX.md"
  exit 1
fi
if ! rg -n "更新时间：" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 缺少更新时间字段"
  exit 1
fi

echo "[2/5] 读取 market_state 版本常量"
expected_contract="$(./venv/bin/python - <<'PY'
from services.market_state_engine.src.version import MARKET_STATE_CONTRACT_VERSION
print(MARKET_STATE_CONTRACT_VERSION)
PY
)"
expected_msl_schema="$(./venv/bin/python - <<'PY'
from services.market_state_engine.src.version import MSL_SCHEMA_VERSION
print(int(MSL_SCHEMA_VERSION))
PY
)"

echo "[3/5] 校验 CONTRACT_INDEX state 版本声明与代码一致"
if ! rg -n "market_state_contract_version:\s*${expected_contract}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 market_state_contract_version=${expected_contract}"
  exit 1
fi
if ! rg -n "market_state_msl_schema_version:\s*${expected_msl_schema}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 market_state_msl_schema_version=${expected_msl_schema}"
  exit 1
fi

echo "[4/5] 校验 contracts/versions/manifest.yaml 与代码常量一致"
./venv/bin/python - <<'PY'
import re
from pathlib import Path

from services.market_state_engine.src.version import MARKET_STATE_CONTRACT_VERSION, MSL_SCHEMA_VERSION

text = Path("contracts/versions/manifest.yaml").read_text(encoding="utf-8")

def read_value(name: str) -> str:
    m = re.search(rf"- name:\s*{re.escape(name)}\s*\n\s*value:\s*\"([^\"]+)\"", text, re.MULTILINE)
    if not m:
        raise SystemExit(f"[失败] manifest 缺少版本项: {name}")
    return str(m.group(1))

if read_value("market_state_contract_version") != str(MARKET_STATE_CONTRACT_VERSION):
    raise SystemExit(
        f"[失败] manifest market_state_contract_version 与代码不一致: "
        f"{read_value('market_state_contract_version')} != {MARKET_STATE_CONTRACT_VERSION}"
    )

if read_value("market_state_msl_schema_version") != str(int(MSL_SCHEMA_VERSION)):
    raise SystemExit(
        f"[失败] manifest market_state_msl_schema_version 与代码不一致: "
        f"{read_value('market_state_msl_schema_version')} != {int(MSL_SCHEMA_VERSION)}"
    )
PY

echo "[5/5] 运行 market_state 版本接口契约测试"
./venv/bin/pytest -q \
  verification/validators/market_state_engine/test_market_state_data_unavailable.py::test_market_state_route_version_exposes_contract_meta

echo "[通过] market_state 合同入口守卫检查完成。"

