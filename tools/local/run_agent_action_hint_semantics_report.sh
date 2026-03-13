#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
OUTPUT_PATH="verification/reports/agent_action_hint_semantics.latest.json"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_action_hint_semantics_report.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --output <path>  输出报告路径（默认 verification/reports/agent_action_hint_semantics.latest.json）
  --help, -h       显示帮助

Description:
  聚合 agent recorder 中 decision_trace + execution_decider 记录，
  统计 minimal 模式下 signal_verdict/signal_direction 对 agent_action_hint 的语义映射命中情况：
  accept + long|short => add；其他 => hold。
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


def _normalize_direction(value: Any) -> str:
    out = str(value or "").strip().lower()
    return out if out in {"long", "short", "none"} else "none"


def _normalize_verdict(value: Any) -> str:
    out = str(value or "").strip().lower()
    return out if out in {"accept", "reject", "uncertain"} else "uncertain"


def _expected_action_hint(verdict: str, direction: str) -> str:
    if verdict == "accept" and direction in {"long", "short"}:
        return "add"
    return "hold"


decision_by_event: dict[str, dict[str, str]] = {}
actual_hint_by_event: dict[str, str] = {}
decision_trace_record_count = 0
execution_decider_record_count = 0

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
    agent_name = str(row.get("agent_name") or "")
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        continue
    payload = dict(row.get("payload") or {})
    if agent_name == "decision_trace":
        decision_trace_record_count += 1
        routing = dict(payload.get("routing") or {})
        if str(routing.get("pipeline_mode") or "").strip().lower() != "minimal":
            continue
        sv = dict(payload.get("signal_verdict") or {})
        verdict = _normalize_verdict(sv.get("verdict"))
        direction = _normalize_direction(sv.get("direction"))
        decision_by_event[event_id] = {
            "verdict": verdict,
            "direction": direction,
            "expected_hint": _expected_action_hint(verdict, direction),
        }
        continue
    if agent_name == "execution_decider":
        execution_decider_record_count += 1
        risk_hints = dict(payload.get("risk_hints") or {})
        hint = str(risk_hints.get("agent_action_hint") or "").strip().lower()
        if hint:
            actual_hint_by_event[event_id] = hint

minimal_decision_count = len(decision_by_event)
expected_add_count = 0
expected_hold_count = 0
actual_hint_available_count = 0
match_count = 0
mismatch_count = 0
missing_actual_hint_count = 0
samples: list[dict[str, str]] = []

for event_id, item in decision_by_event.items():
    expected = str(item.get("expected_hint") or "hold")
    if expected == "add":
        expected_add_count += 1
    else:
        expected_hold_count += 1
    actual = str(actual_hint_by_event.get(event_id) or "").strip().lower()
    if not actual:
        missing_actual_hint_count += 1
        if len(samples) < 10:
            samples.append(
                {
                    "event_id": event_id,
                    "verdict": str(item.get("verdict") or ""),
                    "direction": str(item.get("direction") or ""),
                    "expected_hint": expected,
                    "actual_hint": "",
                    "status": "missing_actual_hint",
                }
            )
        continue
    actual_hint_available_count += 1
    if actual == expected:
        match_count += 1
    else:
        mismatch_count += 1
        if len(samples) < 10:
            samples.append(
                {
                    "event_id": event_id,
                    "verdict": str(item.get("verdict") or ""),
                    "direction": str(item.get("direction") or ""),
                    "expected_hint": expected,
                    "actual_hint": actual,
                    "status": "mismatch",
                }
            )

summary = {
    "decision_trace_record_count": int(decision_trace_record_count),
    "execution_decider_record_count": int(execution_decider_record_count),
    "minimal_decision_count": int(minimal_decision_count),
    "expected_add_count": int(expected_add_count),
    "expected_hold_count": int(expected_hold_count),
    "actual_hint_available_count": int(actual_hint_available_count),
    "missing_actual_hint_count": int(missing_actual_hint_count),
    "match_count": int(match_count),
    "mismatch_count": int(mismatch_count),
    "match_ratio_on_available": round(float(match_count) / float(actual_hint_available_count), 6)
    if actual_hint_available_count
    else 0.0,
}

report = {
    "schema_version": "agent-action-hint-semantics-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "input_path": str(input_path),
    "summary": summary,
    "mismatch_or_missing_samples": samples,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] minimal_decision_count={summary['minimal_decision_count']} "
    f"actual_hint_available_count={summary['actual_hint_available_count']} "
    f"match_count={summary['match_count']} "
    f"mismatch_count={summary['mismatch_count']} "
    f"missing_actual_hint_count={summary['missing_actual_hint_count']}"
)
PY
