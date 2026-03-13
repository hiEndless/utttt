#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_decision_agent_key.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_decision_agent_key_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 agent_name=decision_trace 的 routing.decision_agent_key 字段，
  输出 technical/onchain/liquidation/social_news 四类业务路由命中分布、generic 占位计数、unknown 占比。
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

expected_keys = {"technical", "onchain", "liquidation", "social_news", "generic"}
business_keys = {"technical", "onchain", "liquidation", "social_news"}
decision_trace_record_count = 0
decision_trace_event_ids: set[str] = set()
agent_key_counter: Counter[str] = Counter()
unknown_agent_key_counter: Counter[str] = Counter()

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
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        decision_trace_event_ids.add(event_id)
    payload = dict(row.get("payload") or {})
    routing = dict(payload.get("routing") or {})
    agent_key = str(routing.get("decision_agent_key") or "").strip().lower()
    if not agent_key:
        agent_key = "missing"
    agent_key_counter[agent_key] += 1
    if agent_key not in expected_keys:
        unknown_agent_key_counter[agent_key] += 1

unknown_count = sum(unknown_agent_key_counter.values())
core_four_count = int(sum(agent_key_counter.get(k, 0) for k in business_keys))
report_denom = max(1, decision_trace_record_count)

summary = {
    "decision_trace_record_count": int(decision_trace_record_count),
    "decision_trace_event_count": int(len(decision_trace_event_ids)),
    "technical_count": int(agent_key_counter.get("technical", 0)),
    "onchain_count": int(agent_key_counter.get("onchain", 0)),
    "liquidation_count": int(agent_key_counter.get("liquidation", 0)),
    "social_news_count": int(agent_key_counter.get("social_news", 0)),
    "generic_count": int(agent_key_counter.get("generic", 0)),
    "unknown_count": int(unknown_count),
    "unknown_ratio": round(float(unknown_count) / float(report_denom), 6),
    "core_four_coverage_ratio": round(float(core_four_count) / float(report_denom), 6),
}

agent_key_counts = [
    {"decision_agent_key": key, "count": int(count)}
    for key, count in sorted(agent_key_counter.items(), key=lambda kv: (-kv[1], kv[0]))
]
top_unknown_agent_keys = [
    {"decision_agent_key": key, "count": int(count)}
    for key, count in unknown_agent_key_counter.most_common(10)
]

report = {
    "schema_version": "agent-decision-agent-key-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "agent_key_counts": agent_key_counts,
    "top_unknown_agent_keys": top_unknown_agent_keys,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decision_trace_record_count={summary['decision_trace_record_count']} "
    f"technical={summary['technical_count']} "
    f"onchain={summary['onchain_count']} "
    f"liquidation={summary['liquidation_count']} "
    f"social_news={summary['social_news_count']} "
    f"generic={summary['generic_count']} "
    f"unknown_ratio={summary['unknown_ratio']}"
)
PY
