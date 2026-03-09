#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 CONTRACT_INDEX 文档是否存在"
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少 docs/CONTRACT_INDEX.md"
  exit 1
fi

echo "[2/2] 校验 CONTRACT_INDEX 中的文档路径"
if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi
"$PY_BIN" - <<'PY'
from pathlib import Path
import re
import sys

index_path = Path("docs/CONTRACT_INDEX.md")
root = Path(".").resolve()
text = index_path.read_text(encoding="utf-8")
missing = []

for raw in re.findall(r"`([^`]+)`", text):
    candidate = raw.strip()
    if not candidate:
        continue
    # 仅校验仓库内的 markdown/json 文档路径
    if not (candidate.endswith(".md") or candidate.endswith(".json")):
        continue
    p = (root / candidate).resolve()
    if not p.exists():
        missing.append(candidate)

if missing:
    print("[失败] CONTRACT_INDEX 引用路径不存在：")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print("[通过] CONTRACT_INDEX 引用路径全部有效。")
PY

echo "[通过] contract docs index 守卫检查完成。"
