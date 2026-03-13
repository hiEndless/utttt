#!/usr/bin/env bash
set -euo pipefail

GLOB_PATTERN="verification/reports/agent_signal_decision_replay*.json"
SOURCE_TYPE="social_news"
DAYS=7
PREFIX="nightly"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_agent_signal_decision_replay_trend.sh [options]

Options:
  --glob <pattern>   报告文件 glob（默认 verification/reports/agent_signal_decision_replay*.json）
  --source <type>    来源类型（默认 social_news）
  --days <n>         统计窗口天数（默认 7）
  --prefix <name>    输出前缀（默认 nightly）
  --help, -h         显示帮助

Description:
  读取 signal_decision_replay 报告集合，输出指定 source 的 rule_fallback
  近 N 天趋势摘要（样本数、fallback 数、ratio）。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --glob)
      GLOB_PATTERN="${2:-$GLOB_PATTERN}"
      shift 2
      ;;
    --source)
      SOURCE_TYPE="${2:-$SOURCE_TYPE}"
      shift 2
      ;;
    --days)
      DAYS="${2:-$DAYS}"
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

python3 - "$GLOB_PATTERN" "$SOURCE_TYPE" "$DAYS" "$PREFIX" <<'PY'
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

if len(sys.argv) != 5:
    raise SystemExit("usage: <glob_pattern> <source_type> <days> <prefix>")

glob_pattern = str(sys.argv[1] or "").strip() or "verification/reports/agent_signal_decision_replay*.json"
source_type = str(sys.argv[2] or "").strip().lower() or "social_news"
prefix = str(sys.argv[4] or "").strip() or "nightly"
try:
    days = max(1, int(sys.argv[3]))
except Exception:
    days = 7

now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=days - 1)

by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "fallback": 0, "reports": 0})
loaded_reports = 0

for path in sorted(glob.glob(glob_pattern)):
    p = Path(path)
    if not p.is_file():
        continue
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if str(payload.get("schema_version") or "") != "agent-signal-decision-replay-report-v1":
        continue
    ts_ms = int(payload.get("generated_at_ms") or 0)
    if ts_ms <= 0:
        continue
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    if dt < cutoff:
        continue
    loaded_reports += 1
    day_key = dt.strftime("%Y-%m-%d")
    row_bucket = by_day[day_key]
    row_bucket["reports"] += 1

    rows = [dict(x) for x in list(payload.get("source_decision_mode_counts") or []) if isinstance(x, dict)]
    source_rows = [x for x in rows if str(x.get("signal_source_type") or "").strip().lower() == source_type]
    total = 0
    fallback = 0
    for row in source_rows:
        count = int(row.get("count") or 0)
        mode = str(row.get("decision_mode") or "").strip().lower()
        total += max(0, count)
        if mode == "rule_fallback":
            fallback += max(0, count)
    row_bucket["total"] += total
    row_bucket["fallback"] += fallback

if loaded_reports <= 0:
    print(
        f"[{prefix}] signal_decision_replay_trend "
        f"source={source_type} window_days={days} reports=0 total=0 fallback=0 ratio=0.000000"
    )
    raise SystemExit(0)

days_sorted = sorted(by_day.keys())
total_all = sum(int(by_day[d]["total"]) for d in days_sorted)
fallback_all = sum(int(by_day[d]["fallback"]) for d in days_sorted)
ratio = 0.0 if total_all <= 0 else float(fallback_all) / float(total_all)
latest_day = days_sorted[-1]
latest_total = int(by_day[latest_day]["total"])
latest_fallback = int(by_day[latest_day]["fallback"])
latest_ratio = 0.0 if latest_total <= 0 else float(latest_fallback) / float(latest_total)

print(
    f"[{prefix}] signal_decision_replay_trend "
    f"source={source_type} window_days={days} reports={loaded_reports} "
    f"days={len(days_sorted)} total={total_all} fallback={fallback_all} ratio={ratio:.6f} "
    f"latest_day={latest_day} latest_ratio={latest_ratio:.6f}"
)
PY
