#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_signal_decision_replay.latest.json"
LIMIT=20

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_signal_decision_replay_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  --limit <n>      latest rows 输出条数（默认 20）
  --help, -h       显示帮助

Description:
  回放 decision_trace 的 routing + signal_verdict 结果，输出 source->agent 路由一致性、
  verdict/direction/decision_mode/llm_parse_status 分布，以及最近样例列表。
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
    latest_limit = max(1, int(sys.argv[3]))
except Exception:
    latest_limit = 20

source_expected_agent = {
    "market_indicator": "technical",
    "onchain_wallet": "onchain",
    "large_liquidation": "liquidation",
    "social_news": "social_news",
}


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


decision_trace_record_count = 0
decision_trace_event_ids: set[str] = set()
source_counter: Counter[str] = Counter()
agent_counter: Counter[str] = Counter()
verdict_counter: Counter[str] = Counter()
direction_counter: Counter[str] = Counter()
decision_mode_counter: Counter[str] = Counter()
llm_parse_status_counter: Counter[str] = Counter()
source_decision_mode_counter: Counter[tuple[str, str]] = Counter()
route_match_count = 0
route_mismatch_count = 0
latest_rows: list[dict[str, object]] = []

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
    payload = dict(row.get("payload") or {})
    routing = dict(payload.get("routing") or {})
    signal_verdict = dict(payload.get("signal_verdict") or {})
    event = dict(payload.get("event") or {})

    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        decision_trace_event_ids.add(event_id)
    decision_trace_record_count += 1

    source_type = _norm(event.get("signal_source_type")) or _norm(event.get("source_type"))
    if not source_type:
        source_type = "missing"
    agent_key = _norm(routing.get("decision_agent_key")) or "missing"
    verdict = _norm(signal_verdict.get("verdict")) or "missing"
    direction = _norm(signal_verdict.get("direction")) or "missing"
    decision_mode = _norm(routing.get("decision_mode")) or "missing"
    llm_parse_status = _norm(routing.get("llm_parse_status")) or "missing"
    pipeline_mode = _norm(routing.get("pipeline_mode")) or "missing"

    source_counter[source_type] += 1
    agent_counter[agent_key] += 1
    verdict_counter[verdict] += 1
    direction_counter[direction] += 1
    decision_mode_counter[decision_mode] += 1
    llm_parse_status_counter[llm_parse_status] += 1
    source_decision_mode_counter[(source_type, decision_mode)] += 1

    expected = source_expected_agent.get(source_type)
    route_match = True
    if expected:
        route_match = agent_key == expected
        if route_match:
            route_match_count += 1
        else:
            route_mismatch_count += 1

    latest_rows.append(
        {
            "event_id": event_id,
            "signal_source_type": source_type,
            "expected_agent_key": str(expected or ""),
            "decision_agent_key": agent_key,
            "route_match": bool(route_match),
            "signal_verdict": verdict,
            "signal_direction": direction,
            "decision_mode": decision_mode,
            "llm_parse_status": llm_parse_status,
            "pipeline_mode": pipeline_mode,
            "ts_ms": int(row.get("ts_ms") or 0),
        }
    )

latest_rows_sorted = sorted(latest_rows, key=lambda x: int(x.get("ts_ms") or 0), reverse=True)[:latest_limit]
denom = max(1, route_match_count + route_mismatch_count)

summary = {
    "decision_trace_record_count": int(decision_trace_record_count),
    "decision_trace_event_count": int(len(decision_trace_event_ids)),
    "route_match_count": int(route_match_count),
    "route_mismatch_count": int(route_mismatch_count),
    "route_match_ratio": round(float(route_match_count) / float(denom), 6),
    "accept_count": int(verdict_counter.get("accept", 0)),
    "reject_count": int(verdict_counter.get("reject", 0)),
    "uncertain_count": int(verdict_counter.get("uncertain", 0)),
    "long_count": int(direction_counter.get("long", 0)),
    "short_count": int(direction_counter.get("short", 0)),
    "none_count": int(direction_counter.get("none", 0)),
    "decision_mode_llm_count": int(decision_mode_counter.get("llm", 0)),
    "decision_mode_rule_fallback_count": int(decision_mode_counter.get("rule_fallback", 0)),
    "decision_mode_rule_count": int(decision_mode_counter.get("rule", 0)),
}

report = {
    "schema_version": "agent-signal-decision-replay-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "source_type_counts": [
        {"signal_source_type": k, "count": int(v)} for k, v in sorted(source_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ],
    "decision_agent_key_counts": [
        {"decision_agent_key": k, "count": int(v)} for k, v in sorted(agent_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ],
    "decision_mode_counts": [
        {"decision_mode": k, "count": int(v)}
        for k, v in sorted(decision_mode_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ],
    "llm_parse_status_counts": [
        {"llm_parse_status": k, "count": int(v)}
        for k, v in sorted(llm_parse_status_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ],
    "source_decision_mode_counts": [
        {
            "signal_source_type": src,
            "decision_mode": mode,
            "count": int(cnt),
        }
        for (src, mode), cnt in sorted(
            source_decision_mode_counter.items(),
            key=lambda kv: (-kv[1], kv[0][0], kv[0][1]),
        )
    ],
    "latest_rows": latest_rows_sorted,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decision_trace_record_count={summary['decision_trace_record_count']} "
    f"route_match={summary['route_match_count']} route_mismatch={summary['route_mismatch_count']} "
    f"accept={summary['accept_count']} reject={summary['reject_count']} uncertain={summary['uncertain_count']} "
    f"decision_mode_rule={summary['decision_mode_rule_count']} decision_mode_llm={summary['decision_mode_llm_count']}"
)
PY
