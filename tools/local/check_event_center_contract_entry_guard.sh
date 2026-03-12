#!/usr/bin/env bash
set -euo pipefail

echo "[1/6] 检查 CONTRACT_INDEX 存在且包含更新时间"
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少 docs/CONTRACT_INDEX.md"
  exit 1
fi
if ! rg -n "更新时间：" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 缺少更新时间字段"
  exit 1
fi

echo "[2/6] 读取 event_center 版本常量"
expected_runtime="$(./venv/bin/python - <<'PY'
from services.event_center_new.version import EVENT_CENTER_RUNTIME_CONFIG_VERSION
print(EVENT_CENTER_RUNTIME_CONFIG_VERSION)
PY
)"

echo "[3/6] 校验 CONTRACT_INDEX event_center 版本声明与代码一致"
if ! rg -n "event_center_runtime_config_version:\s*${expected_runtime}" docs/CONTRACT_INDEX.md >/dev/null; then
  echo "[失败] CONTRACT_INDEX 未声明 event_center_runtime_config_version=${expected_runtime}"
  exit 1
fi

echo "[4/6] 校验 contracts/versions/manifest.yaml 与代码常量一致"
./venv/bin/python - <<'PY'
import re
from pathlib import Path

from services.event_center_new.version import EVENT_CENTER_RUNTIME_CONFIG_VERSION

text = Path("contracts/versions/manifest.yaml").read_text(encoding="utf-8")
m = re.search(r"- name:\s*event_center_runtime_config_version\s*\n\s*value:\s*\"([^\"]+)\"", text, re.MULTILINE)
if not m:
    raise SystemExit("[失败] manifest 缺少 event_center_runtime_config_version")
if str(m.group(1)) != str(EVENT_CENTER_RUNTIME_CONFIG_VERSION):
    raise SystemExit(
        f"[失败] manifest event_center_runtime_config_version 与代码不一致: "
        f"{m.group(1)} != {EVENT_CENTER_RUNTIME_CONFIG_VERSION}"
    )
PY

echo "[5/6] 校验 runtime 文档版本声明与代码一致"
if ! rg -n "runtime_config_version:\s*${expected_runtime}" services/event_center_new/docs/runtime.md >/dev/null; then
  echo "[失败] runtime.md 未声明 runtime_config_version=${expected_runtime}"
  exit 1
fi

echo "[6/6] 运行 event_center schema 契约测试"
./venv/bin/pytest -q \
  verification/replay/event_center_new/test_selected_event_schema_contract.py::test_selected_event_schema_required_and_allowed_fields \
  verification/replay/event_center_new/test_replay_summary_schema_contract.py::test_replay_summary_schema_surface

echo "[通过] event_center 合同入口守卫检查完成。"

