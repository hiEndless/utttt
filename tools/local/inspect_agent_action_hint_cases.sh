#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${AGENT_EVENT_RECORDER_JSONL_PATH:-verification/reports/agent_server_new_events.jsonl}"
LIMIT=20
STATUS="all"
FORMAT="table"
OUTPUT_PATH=""

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/inspect_agent_action_hint_cases.sh [options]

Options:
  --input <path>   输入 JSONL 路径（默认 AGENT_EVENT_RECORDER_JSONL_PATH 或 verification/reports/agent_server_new_events.jsonl）
  --limit <n>      输出最近事件条数（默认 20）
  --status <type>  过滤状态（all|ok|mismatch|missing，默认 all）
  --format <type>  输出格式（table|json，默认 table）
  --output <path>  输出文件路径（仅 format=json 时生效）
  --help, -h       显示帮助

Description:
  回放 decision_trace(minimal) + execution_decider，输出 event_id / verdict / direction /
  expected_hint / actual_hint / status 表格，用于快速定位 action_hint 语义映射异常。
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
    --limit)
      LIMIT="${2:-$LIMIT}"
      shift 2
      ;;
    --status)
      STATUS="${2:-$STATUS}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-$FORMAT}"
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

"$PY_BIN" - "$INPUT_PATH" "$LIMIT" "$STATUS" "$FORMAT" "$OUTPUT_PATH" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if len(sys.argv) != 6:
    raise SystemExit("usage: <input_path> <limit> <status> <format> <output_path>")

input_path = Path(sys.argv[1])
try:
    limit = max(1, int(sys.argv[2]))
except Exception:
    limit = 20
status_filter = str(sys.argv[3] or "all").strip().lower()
if status_filter not in {"all", "ok", "mismatch", "missing"}:
    raise SystemExit("[failed] --status must be one of: all|ok|mismatch|missing")
output_format = str(sys.argv[4] or "table").strip().lower()
if output_format not in {"table", "json"}:
    raise SystemExit("[failed] --format must be one of: table|json")
output_path = str(sys.argv[5] or "").strip()
if output_path and output_format != "json":
    raise SystemExit("[failed] --output requires --format json")


def _normalize_direction(value: Any) -> str:
    out = str(value or "").strip().lower()
    if out == "none":
        out = "neutral"
    return out if out in {"long", "short", "neutral"} else "neutral"


def _normalize_verdict(value: Any) -> str:
    out = str(value or "").strip().lower()
    return out if out in {"accept", "reject", "uncertain"} else "uncertain"


def _expected_hint(verdict: str, direction: str) -> str:
    if verdict == "accept" and direction in {"long", "short"}:
        return "add"
    return "hold"


decision_rows: dict[str, dict[str, Any]] = {}
actual_hint_by_event: dict[str, str] = {}

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
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        continue
    payload = dict(row.get("payload") or {})
    agent_name = str(row.get("agent_name") or "")
    if agent_name == "decision_trace":
        routing = dict(payload.get("routing") or {})
        if str(routing.get("pipeline_mode") or "").strip().lower() != "minimal":
            continue
        sv = dict(payload.get("signal_verdict") or {})
        verdict = _normalize_verdict(sv.get("verdict"))
        direction = _normalize_direction(sv.get("direction"))
        decision_rows[event_id] = {
            "event_id": event_id,
            "verdict": verdict,
            "direction": direction,
            "expected_hint": _expected_hint(verdict, direction),
            "actual_hint": "",
            "status": "missing",
            "ts_ms": int(row.get("ts_ms") or 0),
        }
        continue
    if agent_name == "execution_decider":
        risk_hints = dict(payload.get("risk_hints") or {})
        hint = str(risk_hints.get("agent_action_hint") or "").strip().lower()
        if hint:
            actual_hint_by_event[event_id] = hint

rows = []
for event_id, item in decision_rows.items():
    actual = str(actual_hint_by_event.get(event_id) or "").strip().lower()
    expected = str(item.get("expected_hint") or "hold")
    status = "missing"
    if actual:
        status = "ok" if actual == expected else "mismatch"
    row = dict(item)
    row["actual_hint"] = actual
    row["status"] = status
    if status_filter != "all" and status != status_filter:
        continue
    rows.append(row)

rows_sorted = sorted(rows, key=lambda x: int(x.get("ts_ms") or 0), reverse=True)[:limit]

if output_format == "json":
    rendered = json.dumps(
        {
            "schema_version": "agent-action-hint-cases-v1",
            "input_path": str(input_path),
            "status_filter": status_filter,
            "limit": int(limit),
            "count": len(rows_sorted),
            "rows": rows_sorted,
        },
        ensure_ascii=False,
        indent=2,
    )
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print(f"[ok] wrote {out}")
    print(rendered)
else:
    print("event_id\tverdict\tdirection\texpected_hint\tactual_hint\tstatus")
    for row in rows_sorted:
        print(
            f"{str(row.get('event_id') or '')}\t"
            f"{str(row.get('verdict') or '')}\t"
            f"{str(row.get('direction') or '')}\t"
            f"{str(row.get('expected_hint') or '')}\t"
            f"{str(row.get('actual_hint') or '')}\t"
            f"{str(row.get('status') or '')}"
        )
PY
