#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_llm_observe_aggregate_summary.sh [options]

Options:
  --summary <path>  aggregate summary 路径（默认 verification/reports/summary.latest.json）
  --prefix <name>   输出前缀（默认 pipeline）
  --help, -h        显示帮助

Description:
  从 aggregate summary 中提取 signal_decision_llm_observe 指标并输出单行日志。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --summary)
      SUMMARY_PATH="${2:-$SUMMARY_PATH}"
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

python3 - "$SUMMARY_PATH" "$PREFIX" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: <summary_path> <prefix>")

summary_path = Path(sys.argv[1])
prefix = str(sys.argv[2] or "pipeline").strip() or "pipeline"
if not summary_path.is_file():
    raise SystemExit(0)

try:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

record_count = int(payload.get("signal_decision_llm_observe_record_count") or 0)
event_count = int(payload.get("signal_decision_llm_observe_event_count") or 0)
rule_count = int(payload.get("signal_decision_llm_observe_decision_mode_rule_count") or 0)
fallback_count = int(payload.get("signal_decision_llm_observe_decision_mode_rule_fallback_count") or 0)
llm_count = int(payload.get("signal_decision_llm_observe_decision_mode_llm_count") or 0)
mode_missing_count = int(payload.get("signal_decision_llm_observe_decision_mode_missing_count") or 0)
llm_ok_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_llm_ok_count") or 0)
llm_invalid_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_llm_invalid_payload_count") or 0)
rule_only_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_rule_only_count") or 0)
status_not_ok_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_llm_status_not_ok_count") or 0)
not_provided_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_llm_not_provided_count") or 0)
status_missing_count = int(payload.get("signal_decision_llm_observe_llm_parse_status_missing_count") or 0)

print(
    f"[{prefix}] signal_decision_llm_observe_aggregate_summary "
    f"records={record_count} events={event_count} "
    f"mode_rule={rule_count} mode_rule_fallback={fallback_count} mode_llm={llm_count} mode_missing={mode_missing_count} "
    f"status_llm_ok={llm_ok_count} status_llm_invalid_payload={llm_invalid_count} "
    f"status_rule_only={rule_only_count} status_llm_status_not_ok={status_not_ok_count} "
    f"status_llm_not_provided={not_provided_count} status_missing={status_missing_count}"
)
PY
