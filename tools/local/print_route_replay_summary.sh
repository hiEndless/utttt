#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_route_replay_summary.sh [options]

Options:
  --summary <path>  summary 报告路径（默认 verification/reports/summary.latest.json）
  --prefix <name>   输出前缀（默认 pipeline）
  --help, -h        显示帮助

Description:
  从 aggregate summary 中提取 route_replay 指标并输出单行日志：
  ok/count/mismatch/match_ratio。
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

ok = bool(payload.get("route_replay_ok"))
count = int(payload.get("route_replay_count") or 0)
mismatch = int(payload.get("route_replay_mismatch_count") or 0)
match_ratio = float(payload.get("route_replay_match_ratio") or 0.0)

print(
    f"[{prefix}] route_replay_summary "
    f"ok={str(ok).lower()} count={count} mismatch={mismatch} "
    f"match_ratio={match_ratio:.6f}"
)
PY
