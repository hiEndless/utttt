#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 读取当前与上一版本 schema mapping"
changed_files="$(git diff --name-only HEAD~1..HEAD || true)"
if ! printf '%s\n' "${changed_files}" | rg -q '^services/execution_service/docs/.+\.schema\.json$|^services/execution_service/docs/schema_mapping\.json$|^services/execution_service/version\.py$'; then
  echo "[通过] 当前提交未触达 execution schema/version 相关文件，跳过 breaking 升版检查。"
  echo "[2/2] execution breaking 变更升版守卫检查完成。"
  exit 0
fi

./venv/bin/python - <<'PY'
import json
import hashlib
import re
import subprocess
from pathlib import Path

from services.execution_service.version import SCHEMA_MAPPING_VERSION

MAPPING_PATH = "services/execution_service/docs/schema_mapping.json"
version_re = re.compile(r".*-v(\d+)$")


def _major(version: str) -> int:
    m = version_re.match(version.strip())
    if not m:
        raise SystemExit(f"[失败] 非法版本格式: {version}")
    return int(m.group(1))


def _load_current() -> dict:
    return json.loads(Path(MAPPING_PATH).read_text(encoding="utf-8"))


def _load_prev() -> dict | None:
    p = subprocess.run(
        ["git", "show", f"HEAD~1:{MAPPING_PATH}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0 or not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def _index(items: list[dict]) -> dict[str, dict]:
    out = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        if name:
            out[name] = item
    return out


def _item_signature(item: dict) -> tuple:
    fields = item.get("fields") or []
    return (
        str(item.get("schema") or ""),
        str(item.get("code") or ""),
        str(item.get("symbol") or ""),
        tuple(str(x) for x in fields),
    )


def _schema_hash_current(schema_rel: str) -> str | None:
    p = Path(schema_rel)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _schema_hash_prev(schema_rel: str) -> str | None:
    p = subprocess.run(
        ["git", "show", f"HEAD~1:{schema_rel}"],
        capture_output=True,
        text=False,
        check=False,
    )
    if p.returncode != 0:
        return None
    return hashlib.sha256(p.stdout).hexdigest()


cur = _load_current()
prev = _load_prev()
if prev is None:
    print("[通过] 无上一版本 mapping，跳过 breaking 版本递增检查。")
    raise SystemExit(0)

cur_ver = str(cur.get("version") or "").strip()
prev_ver = str(prev.get("version") or "").strip()

cur_items = _index(list(cur.get("items") or []))
prev_items = _index(list(prev.get("items") or []))

breaking_changed = False
breaking_reason = ""
for name, item in cur_items.items():
    if str(item.get("change_policy") or "").strip() != "breaking":
        continue
    prev_item = prev_items.get(name)
    if prev_item is None:
        breaking_changed = True
        breaking_reason = f"{name}: breaking 对象为新增"
        break
    if _item_signature(item) != _item_signature(prev_item):
        breaking_changed = True
        breaking_reason = f"{name}: mapping 签名变更(schema/code/symbol/fields)"
        break
    cur_schema = str(item.get("schema") or "").strip()
    prev_schema = str(prev_item.get("schema") or "").strip()
    if cur_schema != prev_schema:
        breaking_changed = True
        breaking_reason = f"{name}: schema 路径变更({prev_schema} -> {cur_schema})"
        break
    cur_hash = _schema_hash_current(cur_schema)
    prev_hash = _schema_hash_prev(cur_schema)
    if cur_hash != prev_hash:
        breaking_changed = True
        breaking_reason = f"{name}: schema 文件内容 hash 变更"
        break

if not breaking_changed:
    print("[通过] 未检测到 breaking 对象变更，无需 schema mapping 版本递增。")
    raise SystemExit(0)

print(f"[信息] 检测到 breaking 变更触发点: {breaking_reason}")

if _major(cur_ver) <= _major(prev_ver):
    raise SystemExit(
        "[失败] 检测到 breaking 对象变更，但 schema mapping 版本未递增: "
        f"prev={prev_ver}, current={cur_ver}"
    )

if SCHEMA_MAPPING_VERSION != cur_ver:
    raise SystemExit(
        "[失败] execution_service.version.SCHEMA_MAPPING_VERSION "
        f"({SCHEMA_MAPPING_VERSION}) 与 mapping.version({cur_ver}) 不一致"
    )

print("[通过] 检测到 breaking 对象变更且 schema mapping 版本已递增。")
PY

echo "[2/2] execution breaking 变更升版守卫检查完成。"
