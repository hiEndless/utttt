#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
用法:
  bash tools/local/check_contract_docs_index_guard.sh
  bash tools/local/check_contract_docs_index_guard.sh --help

受强约束入口（required_entries）:
  - docs/ALERT_CODES.md
  - docs/contract_docs_index_help_snapshot.txt
  - verification/reports/release_gate_summary_v1.schema.json
  - services/event_center_new/docs/ci_baseline_template.md
  - services/event_center_new/docs/selected_event.schema.json
USAGE
  exit 0
fi

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
# 必需入口清单（按模块分组维护）：
# - docs
#   - docs/ALERT_CODES.md
#   - docs/contract_docs_index_help_snapshot.txt
# - verification
#   - verification/reports/release_gate_summary_v1.schema.json
# - event_center_new
#   - services/event_center_new/docs/ci_baseline_template.md
#   - services/event_center_new/docs/selected_event.schema.json
# - market_state_engine
#   - services/market_state_engine/docs/guard_help_snapshot.txt
required_entries = [
    "docs/ALERT_CODES.md",
    "docs/contract_docs_index_help_snapshot.txt",
    "verification/reports/release_gate_summary_v1.schema.json",
    "services/event_center_new/docs/ci_baseline_template.md",
    "services/event_center_new/docs/selected_event.schema.json",
    "services/market_state_engine/docs/guard_help_snapshot.txt",
]
missing_required = []
duplicate_required = []

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

seen = set()
for item in required_entries:
    if item in seen:
        duplicate_required.append(item)
        continue
    seen.add(item)

if duplicate_required:
    print("[失败] required_entries 存在重复项：")
    for item in duplicate_required:
        print(f"  - {item}")
    sys.exit(1)

for item in sorted(seen):
    if f"`{item}`" not in text:
        missing_required.append(item)

if missing_required:
    print("[失败] CONTRACT_INDEX 缺少必需入口：")
    for item in missing_required:
        print(f"  - {item}")
    sys.exit(1)

print("[通过] CONTRACT_INDEX 引用路径全部有效。")
PY

echo "[附加] 校验入口文档已显式指向 CONTRACT_INDEX"
if ! rg -n "CONTRACT_INDEX\\.md" docs/ARCHITECTURE_NEW.md docs/CONTRACTS_QUICK_REF.md >/dev/null; then
  echo "[失败] 入口文档未统一指向 CONTRACT_INDEX.md"
  exit 1
fi

echo "[通过] contract docs index 守卫检查完成。"
