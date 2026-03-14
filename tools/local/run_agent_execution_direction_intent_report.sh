#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_execution_direction_intent.latest.json"
LIMIT=20

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_execution_direction_intent_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_execution_direction_intent.latest.json）
  --limit <n>      样例最大条数（默认 20）
  --help, -h       显示帮助

Description:
  统计 agent 侧 execution_decider_request 请求体中的 direction_intent 分布，
  用于上线前阻断非规范 none 残留。
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
from collections import Counter
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

rows = input_path.read_text(encoding="utf-8").splitlines() if input_path.is_file() else []
direction_counter: Counter[str] = Counter()
record_count = 0
noncanonical_none_samples: list[dict[str, object]] = []
invalid_samples: list[dict[str, object]] = []

for idx, raw in enumerate(rows, start=1):
    text = str(raw or "").strip()
    if not text:
        continue
    try:
        row = json.loads(text)
    except Exception:
        continue
    if str(row.get("record_type") or "") != "agent_output":
        continue
    if str(row.get("agent_name") or "") != "execution_decider_request":
        continue
    payload = dict(row.get("payload") or {})
    direction = str(payload.get("direction_intent") or "").strip().lower() or "missing"
    direction_counter[direction] += 1
    record_count += 1
    if direction == "none" and len(noncanonical_none_samples) < sample_limit:
        noncanonical_none_samples.append(
            {
                "line_no": idx,
                "event_id": str(row.get("event_id") or ""),
                "direction_intent": direction,
            }
        )
    if direction not in {"long", "short", "neutral", "none"} and len(invalid_samples) < sample_limit:
        invalid_samples.append(
            {
                "line_no": idx,
                "event_id": str(row.get("event_id") or ""),
                "direction_intent": direction,
            }
        )

total = int(sum(direction_counter.values()))
summary = {
    "execution_decider_request_count": int(record_count),
    "direction_intent_total": total,
    "long_count": int(direction_counter.get("long", 0)),
    "short_count": int(direction_counter.get("short", 0)),
    "neutral_count": int(direction_counter.get("neutral", 0)),
    "noncanonical_none_count": int(direction_counter.get("none", 0)),
    "invalid_count": int(
        sum(v for k, v in direction_counter.items() if k not in {"long", "short", "neutral", "none"})
    ),
    "noncanonical_none_ratio": round(float(direction_counter.get("none", 0)) / float(max(1, total)), 6),
}

report = {
    "schema_version": "agent-execution-direction-intent-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "direction_intent_counts": [
        {"direction_intent": k, "count": int(v)} for k, v in sorted(direction_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ],
    "noncanonical_none_samples": noncanonical_none_samples,
    "invalid_samples": invalid_samples,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] request_count={summary['execution_decider_request_count']} total={summary['direction_intent_total']} "
    f"long={summary['long_count']} short={summary['short_count']} neutral={summary['neutral_count']} "
    f"noncanonical_none={summary['noncanonical_none_count']} invalid={summary['invalid_count']}"
)
PY
