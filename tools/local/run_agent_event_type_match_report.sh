#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_event_type_match.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_event_type_match_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_event_type_match.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 agent_name=decision_trace 的 routing.event_type_* 字段，
  输出事件类型命中模式（canonical/alias/empty）占比与 generic 路由下的 unknown event_type top 列表。
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
from collections import Counter
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: <input_path> <output_path>")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

decision_trace_record_count = 0
decision_trace_event_ids: set[str] = set()
match_mode_counter: Counter[str] = Counter()
missing_match_mode_count = 0
unknown_event_counter: Counter[str] = Counter()
unknown_samples: list[dict[str, object]] = []

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
    match_mode = str(routing.get("event_type_match_mode") or "").strip().lower()
    if not match_mode:
        missing_match_mode_count += 1
    else:
        if match_mode not in {"canonical_or_raw", "alias", "empty"}:
            match_mode = "unknown"
        match_mode_counter[match_mode] += 1
    decision_agent_key = str(routing.get("decision_agent_key") or "").strip().lower()
    if decision_agent_key == "generic":
        raw_event_type = str(routing.get("event_type_raw") or "").strip().lower()
        if raw_event_type:
            unknown_event_counter[raw_event_type] += 1
            if len(unknown_samples) < 10:
                unknown_samples.append(
                    {
                        "event_id": event_id or "unknown",
                        "event_type_raw": raw_event_type,
                        "event_type_normalized": str(routing.get("event_type_normalized") or "").strip().lower(),
                        "event_type_match_mode": str(routing.get("event_type_match_mode") or "").strip().lower(),
                        "ts_ms": int(row.get("ts_ms") or 0),
                    }
                )

known_total = (
    int(match_mode_counter.get("canonical_or_raw", 0))
    + int(match_mode_counter.get("alias", 0))
    + int(match_mode_counter.get("empty", 0))
)

summary = {
    "decision_trace_record_count": int(decision_trace_record_count),
    "decision_trace_event_count": int(len(decision_trace_event_ids)),
    "match_mode_canonical_or_raw_count": int(match_mode_counter.get("canonical_or_raw", 0)),
    "match_mode_alias_count": int(match_mode_counter.get("alias", 0)),
    "match_mode_empty_count": int(match_mode_counter.get("empty", 0)),
    "match_mode_unknown_count": int(match_mode_counter.get("unknown", 0)),
    "missing_match_mode_count": int(missing_match_mode_count),
    "match_mode_alias_ratio": round(float(match_mode_counter.get("alias", 0)) / float(known_total), 6) if known_total else 0.0,
    "match_mode_canonical_or_raw_ratio": round(
        float(match_mode_counter.get("canonical_or_raw", 0)) / float(known_total), 6
    )
    if known_total
    else 0.0,
}

top_unknown_event_types = [
    {"event_type_raw": name, "count": int(count)}
    for name, count in unknown_event_counter.most_common(10)
]

report = {
    "schema_version": "agent-event-type-match-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "top_unknown_event_types": top_unknown_event_types,
    "unknown_samples": unknown_samples,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decision_trace_record_count={summary['decision_trace_record_count']} "
    f"alias_count={summary['match_mode_alias_count']} "
    f"canonical_or_raw_count={summary['match_mode_canonical_or_raw_count']} "
    f"missing_match_mode_count={summary['missing_match_mode_count']}"
)
PY

