#!/usr/bin/env bash
set -euo pipefail

DOC="services/event_center_new/docs/ci.md"
BASELINE_TEMPLATE="services/event_center_new/docs/ci_baseline_template.md"
HELP_SNAPSHOT_LINES="services/event_center_new/docs/ci_help_snapshot_lines.txt"
TRIAGE_SNAPSHOT_LINES="services/event_center_new/docs/ci_triage_snapshot_lines.txt"

echo "[1/8] 检查 CI 文档与快照关键行文件存在"
if ! test -f "$DOC"; then
  echo "[失败] 缺少 $DOC"
  exit 1
fi
if ! test -f "$BASELINE_TEMPLATE"; then
  echo "[失败] 缺少 $BASELINE_TEMPLATE"
  exit 1
fi
if ! test -f "$HELP_SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $HELP_SNAPSHOT_LINES"
  exit 1
fi
if ! test -f "$TRIAGE_SNAPSHOT_LINES"; then
  echo "[失败] 缺少 $TRIAGE_SNAPSHOT_LINES"
  exit 1
fi

echo "[2/8] 校验快照关键行文件非空且无重复行"
for snapshot in "$HELP_SNAPSHOT_LINES" "$TRIAGE_SNAPSHOT_LINES"; do
  if [[ ! -s "$snapshot" ]]; then
    echo "[失败] 快照关键行文件为空: $snapshot"
    exit 1
  fi
  duplicate_lines="$(sort "$snapshot" | uniq -d || true)"
  if [[ -n "$duplicate_lines" ]]; then
    echo "[失败] 快照关键行文件存在重复行: $snapshot"
    echo "$duplicate_lines"
    exit 1
  fi
  if rg -n -F "　" "$snapshot" >/dev/null; then
    echo "[失败] 快照关键行文件存在全角空格: $snapshot"
    exit 1
  fi
done

if rg -n "[^\\x00-\\x7F]" "$TRIAGE_SNAPSHOT_LINES" >/dev/null; then
  echo "[失败] $TRIAGE_SNAPSHOT_LINES 必须为 ASCII-only（避免排障命令出现不可见字符）"
  exit 1
fi

echo "[3/8] 校验 CI 文档包含帮助快照关键行"
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    continue
  fi
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档缺少帮助快照关键行: $line"
    exit 1
  fi
done < "$HELP_SNAPSHOT_LINES"

echo "[4/8] 校验 CI 文档包含排障命令快照关键行"
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    continue
  fi
  if ! rg -q -F "$line" "$DOC"; then
    echo "[失败] CI 文档缺少排障命令快照关键行: $line"
    exit 1
  fi
done < "$TRIAGE_SNAPSHOT_LINES"

echo "[附加检查] 校验帮助快照关键行文件包含 CI 文档守卫失败码"
if ! rg -q -F "EC_GUARD_CI_DOC_FAILED" "$HELP_SNAPSHOT_LINES"; then
  echo "[失败] 快照关键行文件缺少 EC_GUARD_CI_DOC_FAILED"
  exit 1
fi

echo "[5/8] 校验 guard_summary 命名约定"
for name in \
  "guard_summary.quick_strict.log" \
  "guard_summary.quick_lenient.log" \
  "guard_summary.full.log"; do
  if ! rg -q -F "$name" "$DOC"; then
    echo "[失败] CI 文档缺少 guard_summary 命名约定: $name"
    exit 1
  fi
  if ! rg -q -F "$name" "$TRIAGE_SNAPSHOT_LINES"; then
    echo "[失败] triage 快照缺少 guard_summary 命名约定: $name"
    exit 1
  fi
done

echo "[6/8] 校验 CI 文档已引用基线模板文件"
if ! rg -q -F "services/event_center_new/docs/ci_baseline_template.md" "$DOC"; then
  echo "[失败] CI 文档未引用基线模板文件: services/event_center_new/docs/ci_baseline_template.md"
  exit 1
fi
if ! rg -q -F "| date | command | mode | result | commit |" "$DOC"; then
  echo "[失败] CI 文档缺少基线记录表头（date/command/mode/result/commit）"
  exit 1
fi

echo "[7/8] 校验基线模板内容完整"
if ! rg -q -F "记录模板（固定）：" "$BASELINE_TEMPLATE"; then
  echo "[失败] 基线模板缺少“记录模板（固定）”标题"
  exit 1
fi
if ! rg -q -F "| date | command | mode | result | commit |" "$BASELINE_TEMPLATE"; then
  echo "[失败] 基线模板缺少标准表头（date/command/mode/result/commit）"
  exit 1
fi
if ! rg -q -F 'result` 只能填写 `pass` 或 `fail`' "$BASELINE_TEMPLATE"; then
  echo "[失败] 基线模板缺少 result 填写规范（pass|fail）"
  exit 1
fi
if ! rg -q -F 'commit` 使用 7~12 位短 SHA' "$BASELINE_TEMPLATE"; then
  echo "[失败] 基线模板缺少 commit 短 SHA 填写规范"
  exit 1
fi
if ! rg -q -F '同一 `commit` 必须同时记录 `quick` 与 `full` 两条基线结果（成对出现）。' "$BASELINE_TEMPLATE"; then
  echo "[失败] 基线模板缺少 quick/full 成对记录规范"
  exit 1
fi

echo "[8/8] 校验基线记录同一 commit 同时包含 quick/full"
if ! test -x ./venv/bin/python; then
  PY_BIN=python3
else
  PY_BIN=./venv/bin/python
fi
"$PY_BIN" - <<'PY'
from pathlib import Path
import re
import sys

doc = Path("services/event_center_new/docs/ci.md").read_text(encoding="utf-8")
pairs: dict[str, set[str]] = {}
for line in doc.splitlines():
    text = line.strip()
    if not text.startswith("| 20"):
        continue
    cols = [x.strip() for x in text.split("|")]
    if len(cols) < 7:
        continue
    mode = cols[3].strip("`")
    commit = cols[5].strip("`")
    if mode not in {"quick", "full"}:
        continue
    if not re.fullmatch(r"[0-9a-f]{7,12}", commit):
        continue
    pairs.setdefault(commit, set()).add(mode)

bad = [commit for commit, modes in pairs.items() if modes != {"quick", "full"}]
if bad:
    print("[失败] 基线记录存在 commit 未同时覆盖 quick/full：")
    for item in sorted(bad):
        print(f"  - {item}")
    sys.exit(1)
print("[通过] 基线记录 commit 覆盖 quick/full 一致。")
PY

echo "[通过] event_center CI 文档快照守卫检查完成。"
