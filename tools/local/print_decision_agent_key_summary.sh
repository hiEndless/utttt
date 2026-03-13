#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
PREFIX="pipeline"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_decision_agent_key_summary.sh [options]

Options:
  --summary <path>  summary 报告路径（默认 verification/reports/summary.latest.json）
  --prefix <name>   输出前缀（默认 pipeline）
  --help, -h        显示帮助

Description:
  从 aggregate summary 中提取 decision_agent_key 指标并输出单行日志：
  technical/onchain/liquidation/social_news/generic/unknown 计数与 ratio。
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

technical = int(payload.get("decision_agent_key_technical_count") or 0)
onchain = int(payload.get("decision_agent_key_onchain_count") or 0)
liquidation = int(payload.get("decision_agent_key_liquidation_count") or 0)
social_news = int(payload.get("decision_agent_key_social_news_count") or 0)
generic = int(payload.get("decision_agent_key_generic_count") or 0)
unknown = int(payload.get("decision_agent_key_unknown_count") or 0)
unknown_ratio = float(payload.get("decision_agent_key_unknown_ratio") or 0.0)
core_four_ratio = float(payload.get("decision_agent_key_core_four_coverage_ratio") or 0.0)

print(
    f"[{prefix}] decision_agent_key_summary "
    f"technical={technical} onchain={onchain} liquidation={liquidation} social_news={social_news} "
    f"generic={generic} unknown={unknown} "
    f"unknown_ratio={unknown_ratio:.6f} core_four_coverage_ratio={core_four_ratio:.6f}"
)
PY
