#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${EXECUTION_DIRECTION_INTENT_INPUT_JSONL:-verification/reports/execution_results.latest.jsonl}"
OUTPUT_PATH="verification/reports/execution_direction_intent_residual.latest.json"
LIMIT=20

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_execution_direction_intent_residual_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 EXECUTION_DIRECTION_INTENT_INPUT_JSONL 或 verification/reports/execution_results.latest.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/execution_direction_intent_residual.latest.json）
  --limit <n>      none 残留样例最大条数（默认 20）
  --help, -h       显示帮助

Description:
  扫描 execution 回放 JSONL 中全部 direction_intent 字段，统计 canonical(neutral) 与 legacy(none) 分布，
  输出 none 残留计数与样例路径，便于灰度期守卫阻断。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --input)
      INPUT_PATH="${2:-$INPUT_PATH}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-$OUTPUT_PATH}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-$LIMIT}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      print_help
      exit 1
      ;;
  esac
done

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - "$INPUT_PATH" "$OUTPUT_PATH" "$LIMIT" <<'PY'
from __future__ import annotations

import json
import time
from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: <input_path> <output_path> <limit>")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
try:
    sample_limit = max(1, int(sys.argv[3]))
except Exception:
    sample_limit = 20


def _walk_direction_intent(obj: object, *, path: str = "$", depth: int = 0) -> list[tuple[str, str]]:
    if depth > 8:
        return []
    out: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}"
            if str(key) == "direction_intent":
                out.append((child_path, str(value or "").strip().lower()))
            out.extend(_walk_direction_intent(value, path=child_path, depth=depth + 1))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            out.extend(_walk_direction_intent(value, path=f"{path}[{idx}]", depth=depth + 1))
    return out


lines = input_path.read_text(encoding="utf-8").splitlines() if input_path.is_file() else []
record_count = 0
total = 0
neutral_count = 0
none_count = 0
long_count = 0
short_count = 0
invalid_count = 0
none_examples: list[dict[str, object]] = []

for idx, raw in enumerate(lines, start=1):
    text = str(raw or "").strip()
    if not text:
        continue
    try:
        row = json.loads(text)
    except Exception:
        continue
    if not isinstance(row, dict):
        continue
    record_count += 1
    pairs = _walk_direction_intent(row)
    if not pairs:
        continue
    event_id = str(row.get("event_id") or row.get("decision_id") or "").strip()
    for path, value in pairs:
        total += 1
        if value == "neutral":
            neutral_count += 1
        elif value == "none":
            none_count += 1
            if len(none_examples) < sample_limit:
                none_examples.append(
                    {
                        "line_no": idx,
                        "event_id": event_id,
                        "path": path,
                        "value": value,
                    }
                )
        elif value == "long":
            long_count += 1
        elif value == "short":
            short_count += 1
        else:
            invalid_count += 1

summary = {
    "record_count": int(record_count),
    "direction_intent_total": int(total),
    "neutral_count": int(neutral_count),
    "none_count": int(none_count),
    "long_count": int(long_count),
    "short_count": int(short_count),
    "invalid_count": int(invalid_count),
    "none_ratio": round(float(none_count) / float(max(1, total)), 6),
    "recommend_action": "migrate_none_producers" if none_count > 0 else "none",
}

report = {
    "schema_version": "execution-direction-intent-residual-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "none_examples": none_examples,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] total={summary['direction_intent_total']} neutral={summary['neutral_count']} "
    f"none={summary['none_count']} long={summary['long_count']} short={summary['short_count']} invalid={summary['invalid_count']}"
)
PY
