#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH="verification/reports/agent_signal_decision_llm_observe.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_llm_observe_summary.sh [options]

Options:
  --report <path>  LLM observe 报告路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
  --prefix <name>  输出前缀（默认 pipeline）
  --help, -h       显示帮助

Description:
  从 LLM observe 报告中提取 decision_mode / llm_parse_status 指标并输出单行日志。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --report)
      REPORT_PATH="${2:-$REPORT_PATH}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-$PREFIX}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

python3 - "$REPORT_PATH" "$PREFIX" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: <report_path> <prefix>")

report_path = Path(sys.argv[1])
prefix = str(sys.argv[2] or "pipeline").strip() or "pipeline"
if not report_path.is_file():
    raise SystemExit(0)

try:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

summary = dict(payload.get("summary") or {})
record_count = int(summary.get("decision_trace_record_count") or 0)
event_count = int(summary.get("decision_trace_event_count") or 0)
decision_mode = dict(summary.get("decision_mode") or {})
llm_parse_status = dict(summary.get("llm_parse_status") or {})

print(
    f"[{prefix}] signal_decision_llm_observe_summary "
    f"records={record_count} events={event_count} "
    f"decision_mode={json.dumps(decision_mode, ensure_ascii=False, sort_keys=True)} "
    f"llm_parse_status={json.dumps(llm_parse_status, ensure_ascii=False, sort_keys=True)}"
)
PY
