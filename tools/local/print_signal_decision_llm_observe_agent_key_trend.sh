#!/usr/bin/env bash
set -euo pipefail

GLOB_PATTERN="verification/reports/agent_signal_decision_llm_observe*.json"
DAYS=7
MIN_RATIO=0.15
MIN_CONSECUTIVE_DAYS=3
AGENT_KEYS="social_news,onchain,technical,liquidation"
OUTPUT_PATH=""
RECOMMENDATION_OUTPUT_PATH=""
PREFIX="nightly"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/print_signal_decision_llm_observe_agent_key_trend.sh [options]

Options:
  --glob <pattern>            报告文件 glob（默认 verification/reports/agent_signal_decision_llm_observe*.json）
  --days <n>                  统计窗口天数（默认 7）
  --min-ratio <float>         llm_ok_ratio 告警阈值（默认 0.15）
  --min-consecutive-days <n>  连续低于阈值天数（默认 3）
  --agent-keys <csv>          关注 agent_key（默认 social_news,onchain,technical,liquidation）
  --output <path>             趋势 JSON 输出路径（默认不落盘）
  --recommendation-output <path>
                              recommendation JSON 输出路径（默认不落盘）
  --prefix <name>             输出前缀（默认 nightly）
  --help, -h                  显示帮助

Description:
  聚合 LLM observe 报告，按 decision_agent_key 输出近 N 天 llm_ok_ratio 趋势，
  并在连续低于阈值时输出 [warn]（非阻断）。
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
    --days)
      DAYS="${2:-$DAYS}"
      shift 2
      ;;
    --min-ratio)
      MIN_RATIO="${2:-$MIN_RATIO}"
      shift 2
      ;;
    --min-consecutive-days)
      MIN_CONSECUTIVE_DAYS="${2:-$MIN_CONSECUTIVE_DAYS}"
      shift 2
      ;;
    --agent-keys)
      AGENT_KEYS="${2:-$AGENT_KEYS}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-$OUTPUT_PATH}"
      shift 2
      ;;
    --recommendation-output)
      RECOMMENDATION_OUTPUT_PATH="${2:-$RECOMMENDATION_OUTPUT_PATH}"
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

python3 - "$GLOB_PATTERN" "$DAYS" "$MIN_RATIO" "$MIN_CONSECUTIVE_DAYS" "$AGENT_KEYS" "$OUTPUT_PATH" "$RECOMMENDATION_OUTPUT_PATH" "$PREFIX" <<'PY'
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

if len(sys.argv) != 9:
    raise SystemExit("usage: <glob> <days> <min_ratio> <min_consecutive_days> <agent_keys> <output> <recommendation_output> <prefix>")

glob_pattern = str(sys.argv[1] or "").strip() or "verification/reports/agent_signal_decision_llm_observe*.json"
prefix = str(sys.argv[8] or "nightly").strip() or "nightly"
output_path = str(sys.argv[6] or "").strip()
recommendation_output_path = str(sys.argv[7] or "").strip()
agent_keys_raw = str(sys.argv[5] or "").strip()
agent_keys = [x.strip().lower() for x in agent_keys_raw.split(",") if x.strip()]
if not agent_keys:
    agent_keys = ["social_news", "onchain", "technical", "liquidation"]
try:
    days = max(1, int(str(sys.argv[2] or "7")))
except Exception:
    days = 7
try:
    min_ratio = float(str(sys.argv[3] or "0.15"))
except Exception:
    min_ratio = 0.15
try:
    min_consecutive_days = max(1, int(str(sys.argv[4] or "3")))
except Exception:
    min_consecutive_days = 3

rows: list[tuple[datetime, dict]] = []
for path in sorted(glob.glob(glob_pattern)):
    p = Path(path)
    if not p.is_file():
        continue
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if str(payload.get("schema_version") or "") != "agent-signal-decision-llm-observe-report-v1":
        continue
    ts_ms = int(payload.get("generated_at_ms") or 0)
    if ts_ms <= 0:
        continue
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    rows.append((dt, payload))

if not rows:
    print(f"[{prefix}] signal_decision_llm_observe_agent_key_trend reports=0")
    out = {
        "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-v1",
        "reports": 0,
        "window_days": int(days),
        "agent_keys": list(agent_keys),
        "rows": [],
    }
    if output_path:
        outp = Path(output_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[ok] wrote {outp}")
    if recommendation_output_path:
        rec = {
            "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1",
            "status": "skip",
            "reason": "no_reports",
            "reports": 0,
            "agent_keys": list(agent_keys),
            "recommend_action": "none",
            "warn_agent_keys": [],
        }
        recp = Path(recommendation_output_path)
        recp.parent.mkdir(parents=True, exist_ok=True)
        recp.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[ok] wrote {recp}")
    raise SystemExit(0)

anchor = max(dt for dt, _ in rows)
cutoff = anchor - timedelta(days=days - 1)
rows = [(dt, payload) for dt, payload in rows if dt >= cutoff]

by_key_day: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"records": 0, "llm_ok": 0}))
report_count = len(rows)
for dt, payload in rows:
    day = dt.strftime("%Y-%m-%d")
    per_key = [dict(x) for x in list(payload.get("per_agent_key") or []) if isinstance(x, dict)]
    by_name = {str(x.get("decision_agent_key") or "").strip().lower(): x for x in per_key}
    for key in agent_keys:
        row = dict(by_name.get(key) or {})
        records = int(row.get("record_count") or 0)
        parse_status = dict(row.get("llm_parse_status") or {})
        llm_ok = int(parse_status.get("llm_ok") or 0)
        slot = by_key_day[key][day]
        slot["records"] += max(0, records)
        slot["llm_ok"] += max(0, llm_ok)

result_rows: list[dict] = []
warn_agent_keys: list[str] = []
for key in agent_keys:
    days_sorted = sorted(by_key_day[key].keys())
    total_records = sum(int(by_key_day[key][d]["records"]) for d in days_sorted)
    total_llm_ok = sum(int(by_key_day[key][d]["llm_ok"]) for d in days_sorted)
    ratio = 0.0 if total_records <= 0 else round(float(total_llm_ok) / float(total_records), 6)
    latest_day = days_sorted[-1] if days_sorted else ""
    latest_records = int(by_key_day[key][latest_day]["records"]) if latest_day else 0
    latest_llm_ok = int(by_key_day[key][latest_day]["llm_ok"]) if latest_day else 0
    latest_ratio = 0.0 if latest_records <= 0 else round(float(latest_llm_ok) / float(latest_records), 6)
    consecutive_low_days = 0
    for day in reversed(days_sorted):
        rec = int(by_key_day[key][day]["records"])
        ok = int(by_key_day[key][day]["llm_ok"])
        day_ratio = 0.0 if rec <= 0 else float(ok) / float(rec)
        if day_ratio < min_ratio:
            consecutive_low_days += 1
        else:
            break
    status = "warn" if latest_ratio < min_ratio and consecutive_low_days >= min_consecutive_days else "ok"
    if status == "warn":
        warn_agent_keys.append(key)
    print(
        f"[{status}] {prefix} signal_decision_llm_observe_agent_key_trend "
        f"agent_key={key} reports={report_count} days={len(days_sorted)} "
        f"records={total_records} llm_ok={total_llm_ok} ratio={ratio:.6f} "
        f"latest_day={latest_day or 'na'} latest_ratio={latest_ratio:.6f} "
        f"consecutive_low_days={consecutive_low_days} min_ratio={min_ratio:.6f} "
        f"min_consecutive_days={min_consecutive_days}"
    )
    result_rows.append(
        {
            "agent_key": key,
            "reports": int(report_count),
            "days": int(len(days_sorted)),
            "records": int(total_records),
            "llm_ok": int(total_llm_ok),
            "ratio": float(ratio),
            "latest_day": latest_day,
            "latest_ratio": float(latest_ratio),
            "consecutive_low_days": int(consecutive_low_days),
            "status": status,
        }
    )

out = {
    "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-v1",
    "generated_at_ms": int(anchor.timestamp() * 1000),
    "window_days": int(days),
    "min_ratio": float(round(min_ratio, 6)),
    "min_consecutive_days": int(min_consecutive_days),
    "agent_keys": list(agent_keys),
    "reports": int(report_count),
    "rows": result_rows,
}
if output_path:
    outp = Path(output_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {outp}")

if recommendation_output_path:
    status = "recommend" if warn_agent_keys else "hold"
    recommendation = {
        "schema_version": "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1",
        "status": status,
        "reason": "low_llm_ok_ratio_consecutive_days" if warn_agent_keys else "all_agent_keys_stable",
        "reports": int(report_count),
        "window_days": int(days),
        "min_ratio": float(round(min_ratio, 6)),
        "min_consecutive_days": int(min_consecutive_days),
        "agent_keys": list(agent_keys),
        "warn_agent_keys": sorted(warn_agent_keys),
        "recommend_action": "review_llm_prompt_or_model_routing" if warn_agent_keys else "none",
    }
    recp = Path(recommendation_output_path)
    recp.parent.mkdir(parents=True, exist_ok=True)
    recp.write_text(json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {recp}")
PY
