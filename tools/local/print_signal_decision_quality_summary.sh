#!/usr/bin/env bash
set -euo pipefail

REPORT_PATH="verification/reports/agent_signal_decision_replay.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_quality_summary.sh [options]

Options:
  --report <path>   signal decision replay 报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  --prefix <name>   输出前缀（默认 pipeline）
  --help, -h        显示帮助

Description:
  从 signal decision replay 报告提取“按来源”的决策质量分布：
  - decision_mode: llm/rule_fallback/rule
  - llm_parse_status: llm_ok
  - signal_verdict: accept/reject/uncertain
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
from collections import defaultdict
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

if str(payload.get("schema_version") or "") != "agent-signal-decision-replay-report-v1":
    raise SystemExit(0)

sources = set()
mode_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
parse_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
verdict_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

for row in list(payload.get("source_decision_mode_counts") or []):
    if not isinstance(row, dict):
        continue
    src = str(row.get("signal_source_type") or "").strip().lower()
    mode = str(row.get("decision_mode") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src:
        continue
    sources.add(src)
    mode_map[src][mode] += max(0, cnt)

for row in list(payload.get("source_llm_parse_status_counts") or []):
    if not isinstance(row, dict):
        continue
    src = str(row.get("signal_source_type") or "").strip().lower()
    status = str(row.get("llm_parse_status") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src:
        continue
    sources.add(src)
    parse_map[src][status] += max(0, cnt)

for row in list(payload.get("source_verdict_counts") or []):
    if not isinstance(row, dict):
        continue
    src = str(row.get("signal_source_type") or "").strip().lower()
    verdict = str(row.get("signal_verdict") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src:
        continue
    sources.add(src)
    verdict_map[src][verdict] += max(0, cnt)

for src in sorted(sources):
    llm = int(mode_map[src].get("llm", 0))
    rule_fallback = int(mode_map[src].get("rule_fallback", 0))
    rule = int(mode_map[src].get("rule", 0))
    total = max(0, llm + rule_fallback + rule + int(mode_map[src].get("missing", 0)))
    llm_ok = int(parse_map[src].get("llm_ok", 0))
    accept = int(verdict_map[src].get("accept", 0))
    reject = int(verdict_map[src].get("reject", 0))
    uncertain = int(verdict_map[src].get("uncertain", 0))
    fallback_ratio = 0.0 if total <= 0 else float(rule_fallback) / float(total)
    print(
        f"[{prefix}] signal_decision_quality_summary "
        f"source={src} total={total} llm={llm} rule_fallback={rule_fallback} rule={rule} "
        f"llm_ok={llm_ok} accept={accept} reject={reject} uncertain={uncertain} "
        f"rule_fallback_ratio={fallback_ratio:.6f}"
    )
PY
