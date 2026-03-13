#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH="verification/reports/agent_signal_decision_replay.latest.json"
PREFIX="quick"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_replay_summary.sh [options]

Options:
  --report <path>  报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  --prefix <name>  输出前缀（默认 quick）
  --help, -h       显示帮助

Description:
  从 signal decision replay 报告输出单行业务摘要：
  route_match/mismatch + verdict + decision_mode 分布。
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
prefix = str(sys.argv[2] or "quick").strip() or "quick"
if not report_path.is_file():
    raise SystemExit(0)

try:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

summary = dict(payload.get("summary") or {})
print(
    f"[{prefix}] signal_decision_replay_summary "
    f"records={int(summary.get('decision_trace_record_count') or 0)} "
    f"route_match={int(summary.get('route_match_count') or 0)} "
    f"route_mismatch={int(summary.get('route_mismatch_count') or 0)} "
    f"route_match_ratio={float(summary.get('route_match_ratio') or 0.0):.6f} "
    f"accept={int(summary.get('accept_count') or 0)} "
    f"reject={int(summary.get('reject_count') or 0)} "
    f"uncertain={int(summary.get('uncertain_count') or 0)} "
    f"rule={int(summary.get('decision_mode_rule_count') or 0)} "
    f"rule_fallback={int(summary.get('decision_mode_rule_fallback_count') or 0)} "
    f"llm={int(summary.get('decision_mode_llm_count') or 0)}"
)
PY
