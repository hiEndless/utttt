#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_decision_trace_schema_guard.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_decision_trace_schema_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 agent_name=decision_trace_schema_guard 的记录，
  生成运行时 schema 漂移告警摘要（仅观测，不阻断业务链路）。
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

events: dict[str, dict[str, Any]] = {}
total_records = 0
invalid_records = 0

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
    if str(row.get("agent_name") or "") != "decision_trace_schema_guard":
        continue
    total_records += 1
    payload = dict(row.get("payload") or {})
    status = str(payload.get("status") or "")
    if status != "invalid":
        continue
    invalid_records += 1
    event_id = str(row.get("event_id") or "unknown")
    item = events.setdefault(
        event_id,
        {
            "event_id": event_id,
            "hits": 0,
            "max_error_count": 0,
            "latest_ts_ms": 0,
            "sample_errors": [],
        },
    )
    item["hits"] = int(item.get("hits") or 0) + 1
    err_cnt = int(payload.get("error_count") or 0)
    item["max_error_count"] = max(int(item.get("max_error_count") or 0), err_cnt)
    item["latest_ts_ms"] = max(int(item.get("latest_ts_ms") or 0), int(row.get("ts_ms") or 0))
    if not item.get("sample_errors"):
        item["sample_errors"] = [str(x) for x in list(payload.get("errors") or []) if x][:5]

report = {
    "schema_version": "agent-decision-trace-schema-guard-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": {
        "total_guard_records": int(total_records),
        "invalid_guard_records": int(invalid_records),
        "affected_event_count": int(len(events)),
    },
    "events": sorted(events.values(), key=lambda x: (int(x.get("latest_ts_ms") or 0), str(x.get("event_id") or "")), reverse=True),
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] total_guard_records={report['summary']['total_guard_records']} "
    f"invalid_guard_records={report['summary']['invalid_guard_records']} "
    f"affected_event_count={report['summary']['affected_event_count']}"
)
PY
