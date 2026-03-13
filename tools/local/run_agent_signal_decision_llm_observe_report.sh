#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_signal_decision_llm_observe.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_signal_decision_llm_observe_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 agent_name=decision_trace 的 routing 决策字段，
  输出 decision_mode / llm_parse_status 总览与按 decision_agent_key 分组分布，
  用于 AGENT_SIGNAL_DECISION_LLM_MODE=observe 阶段评估 LLM 接管时机。
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
from collections import Counter, defaultdict
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: <input_path> <output_path>")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

decision_trace_record_count = 0
decision_trace_event_ids: set[str] = set()
mode_counter: Counter[str] = Counter()
parse_status_counter: Counter[str] = Counter()
missing_mode_count = 0
missing_parse_status_count = 0
by_agent_key: dict[str, dict[str, Counter[str] | int]] = defaultdict(
    lambda: {
        "record_count": 0,
        "decision_mode": Counter(),
        "llm_parse_status": Counter(),
    }
)

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
    agent_key = str(routing.get("decision_agent_key") or "").strip().lower() or "unknown"

    mode = str(routing.get("decision_mode") or "").strip().lower()
    if not mode:
        missing_mode_count += 1
        mode = "missing"
    mode_counter[mode] += 1

    parse_status = str(routing.get("llm_parse_status") or "").strip().lower()
    if not parse_status:
        missing_parse_status_count += 1
        parse_status = "missing"
    parse_status_counter[parse_status] += 1

    group = by_agent_key[agent_key]
    group["record_count"] = int(group["record_count"]) + 1
    group["decision_mode"][mode] += 1  # type: ignore[index]
    group["llm_parse_status"][parse_status] += 1  # type: ignore[index]

per_agent_key = []
for key in sorted(by_agent_key.keys()):
    group = by_agent_key[key]
    per_agent_key.append(
        {
            "decision_agent_key": key,
            "record_count": int(group["record_count"]),
            "decision_mode": dict(sorted((group["decision_mode"]).items())),  # type: ignore[union-attr]
            "llm_parse_status": dict(sorted((group["llm_parse_status"]).items())),  # type: ignore[union-attr]
        }
    )

report = {
    "schema_version": "agent-signal-decision-llm-observe-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": {
        "decision_trace_record_count": int(decision_trace_record_count),
        "decision_trace_event_count": int(len(decision_trace_event_ids)),
        "missing_decision_mode_count": int(missing_mode_count),
        "missing_llm_parse_status_count": int(missing_parse_status_count),
        "decision_mode": dict(sorted(mode_counter.items())),
        "llm_parse_status": dict(sorted(parse_status_counter.items())),
    },
    "per_agent_key": per_agent_key,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decision_trace_record_count={report['summary']['decision_trace_record_count']} "
    f"decision_mode={report['summary']['decision_mode']} "
    f"llm_parse_status={report['summary']['llm_parse_status']}"
)
PY
