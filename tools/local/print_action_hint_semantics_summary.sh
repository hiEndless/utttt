#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_action_hint_semantics_summary.sh [options]

Options:
  --summary <path>  summary 报告路径（默认 verification/reports/summary.latest.json）
  --prefix <name>   输出前缀（默认 pipeline）
  --help, -h        显示帮助

Description:
  从 aggregate summary 中提取 action_hint_semantics 指标并输出单行日志：
  minimal 决策数、可比对样本数、match/mismatch/missing 与 match_ratio。
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

minimal_decision_count = int(payload.get("action_hint_semantics_minimal_decision_count") or 0)
actual_hint_available_count = int(payload.get("action_hint_semantics_actual_hint_available_count") or 0)
match_count = int(payload.get("action_hint_semantics_match_count") or 0)
mismatch_count = int(payload.get("action_hint_semantics_mismatch_count") or 0)
missing_actual_hint_count = int(payload.get("action_hint_semantics_missing_actual_hint_count") or 0)
match_ratio_on_available = float(payload.get("action_hint_semantics_match_ratio_on_available") or 0.0)

print(
    f"[{prefix}] action_hint_semantics_summary "
    f"minimal_decision_count={minimal_decision_count} "
    f"actual_hint_available_count={actual_hint_available_count} "
    f"match_count={match_count} mismatch_count={mismatch_count} "
    f"missing_actual_hint_count={missing_actual_hint_count} "
    f"match_ratio_on_available={match_ratio_on_available:.6f}"
)
PY
