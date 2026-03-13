#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_pipeline_mode.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_pipeline_mode_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 agent_name=decision_trace 的 routing.pipeline_mode，
  输出 legacy/minimal 占比与缺失字段计数，便于灰度观测最小链路切换情况。
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

"$PY_BIN" - "$INPUT_PATH" "$OUTPUT_PATH" <<'PY'
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: <input_path> <output_path>")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

legacy_count = 0
minimal_count = 0
unknown_count = 0
missing_pipeline_mode_count = 0
decision_trace_record_count = 0
decision_trace_event_ids: set[str] = set()
unknown_samples: list[dict[str, Any]] = []

if input_path.is_file():
    lines = input_path.read_text(encoding="utf-8").splitlines()
else:
    lines = []

for raw in lines:
    text = str(raw or "").strip()
    if not text:
        continue
    try:
        row = json.loads(text)
    except Exception:
        continue
    if str(row.get("record_type") or "") != "agent_output":
        continue
    if str(row.get("agent_name") or "") != "decision_trace":
        continue
    decision_trace_record_count += 1
    event_id = str(row.get("event_id") or "")
    if event_id:
        decision_trace_event_ids.add(event_id)
    payload = dict(row.get("payload") or {})
    routing = dict(payload.get("routing") or {})
    mode = str(routing.get("pipeline_mode") or "").strip()
    if not mode:
        missing_pipeline_mode_count += 1
        continue
    if mode == "legacy":
        legacy_count += 1
        continue
    if mode == "minimal":
        minimal_count += 1
        continue
    unknown_count += 1
    if len(unknown_samples) < 5:
        unknown_samples.append(
            {
                "event_id": event_id or "unknown",
                "pipeline_mode": mode,
                "ts_ms": int(row.get("ts_ms") or 0),
            }
        )

known_total = legacy_count + minimal_count
legacy_ratio = round(float(legacy_count) / float(known_total), 6) if known_total else 0.0
minimal_ratio = round(float(minimal_count) / float(known_total), 6) if known_total else 0.0

report = {
    "schema_version": "agent-pipeline-mode-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": {
        "decision_trace_record_count": int(decision_trace_record_count),
        "decision_trace_event_count": int(len(decision_trace_event_ids)),
        "legacy_count": int(legacy_count),
        "minimal_count": int(minimal_count),
        "unknown_count": int(unknown_count),
        "missing_pipeline_mode_count": int(missing_pipeline_mode_count),
        "legacy_ratio": legacy_ratio,
        "minimal_ratio": minimal_ratio,
    },
    "unknown_samples": unknown_samples,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decision_trace_record_count={report['summary']['decision_trace_record_count']} "
    f"legacy_count={report['summary']['legacy_count']} "
    f"minimal_count={report['summary']['minimal_count']} "
    f"missing_pipeline_mode_count={report['summary']['missing_pipeline_mode_count']}"
)
PY
