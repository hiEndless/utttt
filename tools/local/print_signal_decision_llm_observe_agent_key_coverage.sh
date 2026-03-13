#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH="verification/reports/agent_signal_decision_llm_observe.latest.json"
PREFIX="nightly"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_llm_observe_agent_key_coverage.sh [options]

Options:
  --report <path>  LLM observe 报告路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
  --prefix <name>  输出前缀（默认 nightly）
  --help, -h       显示帮助

Description:
  从 LLM observe 报告按 decision_agent_key 输出 llm_ok 覆盖率摘要。
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
prefix = str(sys.argv[2] or "nightly").strip() or "nightly"
if not report_path.is_file():
    raise SystemExit(0)

try:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

rows = [dict(x) for x in list(payload.get("per_agent_key") or []) if isinstance(x, dict)]
if not rows:
    print(f"[{prefix}] signal_decision_llm_observe_agent_key_coverage no_data")
    raise SystemExit(0)

for row in rows:
    key = str(row.get("decision_agent_key") or "unknown").strip().lower() or "unknown"
    record_count = int(row.get("record_count") or 0)
    parse_status = dict(row.get("llm_parse_status") or {})
    llm_ok = int(parse_status.get("llm_ok") or 0)
    ratio = 0.0 if record_count <= 0 else round(float(llm_ok) / float(record_count), 6)
    print(
        f"[{prefix}] signal_decision_llm_observe_agent_key_coverage "
        f"agent_key={key} records={record_count} llm_ok={llm_ok} llm_ok_ratio={ratio:.6f}"
    )
PY
