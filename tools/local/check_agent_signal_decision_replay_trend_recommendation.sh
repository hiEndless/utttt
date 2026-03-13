#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_agent_signal_decision_replay_trend_recommendation.sh [trend_report_json] [recommend_ratio] [min_consecutive_days] [min_total_samples] [output_json]

Description:
  读取 signal_decision_replay 趋势报告，满足条件时输出收紧阈值建议标记（不阻断）：
  [recommend] tighten_social_news_fallback_ratio_to_0_80 ...

Args:
  trend_report_json      趋势报告路径（默认 verification/reports/agent_signal_decision_replay_trend.latest.json）
  recommend_ratio        建议触发阈值（默认 0.70）
  min_consecutive_days   连续天数要求（默认 3）
  min_total_samples      总样本数下限（默认 20）
  output_json            建议输出路径（默认不落盘）

Exit Codes:
  exit 0  正常执行（包含 recommend/hold/skip）
  exit 2  输入参数非法
  exit 3  报告解析失败
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

TREND_REPORT="${1:-verification/reports/agent_signal_decision_replay_trend.latest.json}"
RECOMMEND_RATIO_RAW="${2:-0.70}"
MIN_CONSECUTIVE_DAYS_RAW="${3:-3}"
MIN_TOTAL_SAMPLES_RAW="${4:-20}"
OUTPUT_PATH_RAW="${5:-}"

"$PY_BIN" - <<'PY' "$TREND_REPORT" "$RECOMMEND_RATIO_RAW" "$MIN_CONSECUTIVE_DAYS_RAW" "$MIN_TOTAL_SAMPLES_RAW" "$OUTPUT_PATH_RAW"
from __future__ import annotations

import json
import sys
from pathlib import Path

trend_report = Path(sys.argv[1])
recommend_ratio_raw = str(sys.argv[2] or "0.70").strip()
min_consecutive_days_raw = str(sys.argv[3] or "3").strip()
min_total_samples_raw = str(sys.argv[4] or "20").strip()
output_path_raw = str(sys.argv[5] or "").strip()

try:
    recommend_ratio = float(recommend_ratio_raw)
    min_consecutive_days = max(1, int(min_consecutive_days_raw))
    min_total_samples = max(1, int(min_total_samples_raw))
except Exception:
    print("[skip] trend_recommendation invalid args")
    raise SystemExit(2)

output_payload: dict[str, object] = {
    "schema_version": "agent-signal-decision-replay-trend-recommendation-v1",
    "status": "skip",
    "recommend_action": "none",
    "source_type": "social_news",
    "recommend_ratio": float(recommend_ratio),
    "min_consecutive_days": int(min_consecutive_days),
    "min_total_samples": int(min_total_samples),
}

def _write_output() -> None:
    if not output_path_raw:
        return
    out = Path(output_path_raw)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {out}")

if not trend_report.is_file():
    print(f"[skip] trend_recommendation report missing: {trend_report}")
    output_payload["reason"] = "report_missing"
    output_payload["trend_report_path"] = str(trend_report)
    _write_output()
    raise SystemExit(0)

try:
    payload = json.loads(trend_report.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] trend_recommendation invalid json: {exc}")
    output_payload["status"] = "failed"
    output_payload["reason"] = "invalid_json"
    output_payload["trend_report_path"] = str(trend_report)
    output_payload["error"] = str(exc)
    _write_output()
    raise SystemExit(3)

if str(payload.get("schema_version") or "") != "agent-signal-decision-replay-trend-v1":
    print(f"[skip] trend_recommendation unsupported schema_version={payload.get('schema_version')}")
    output_payload["reason"] = "unsupported_schema_version"
    output_payload["trend_report_path"] = str(trend_report)
    output_payload["schema_version_found"] = str(payload.get("schema_version") or "")
    _write_output()
    raise SystemExit(0)

source_type = str(payload.get("source_type") or "social_news").strip().lower()
ratio = float(payload.get("ratio") or 0.0)
total = int(payload.get("total") or 0)
days = int(payload.get("days") or 0)
latest_ratio = float(payload.get("latest_ratio") or 0.0)
daily_rows = [dict(x) for x in list(payload.get("daily_rows") or []) if isinstance(x, dict)]
output_payload["trend_report_path"] = str(trend_report)
output_payload["source_type"] = source_type
output_payload["ratio"] = float(ratio)
output_payload["latest_ratio"] = float(latest_ratio)
output_payload["total"] = int(total)
output_payload["days"] = int(days)

consecutive = 0
for row in reversed(daily_rows):
    row_ratio = float(row.get("ratio") or 0.0)
    row_total = int(row.get("total") or 0)
    if row_total > 0 and row_ratio < recommend_ratio:
        consecutive += 1
    else:
        break

if total < min_total_samples:
    print(
        f"[hold] trend_recommendation source={source_type} "
        f"reason=low_total_samples total={total} min_total_samples={min_total_samples}"
    )
    output_payload["status"] = "hold"
    output_payload["reason"] = "low_total_samples"
    output_payload["recommend_action"] = "none"
    output_payload["consecutive_days"] = int(consecutive)
    _write_output()
    raise SystemExit(0)

if days < min_consecutive_days:
    print(
        f"[hold] trend_recommendation source={source_type} "
        f"reason=insufficient_days days={days} min_consecutive_days={min_consecutive_days}"
    )
    output_payload["status"] = "hold"
    output_payload["reason"] = "insufficient_days"
    output_payload["recommend_action"] = "none"
    output_payload["consecutive_days"] = int(consecutive)
    _write_output()
    raise SystemExit(0)

if ratio < recommend_ratio and latest_ratio < recommend_ratio and consecutive >= min_consecutive_days:
    print(
        "[recommend] tighten_social_news_fallback_ratio_to_0_80 "
        f"source={source_type} ratio={ratio:.6f} latest_ratio={latest_ratio:.6f} "
        f"consecutive_days={consecutive} total={total} "
        f"recommend_ratio={recommend_ratio:.6f} min_total_samples={min_total_samples}"
    )
    output_payload["status"] = "recommend"
    output_payload["reason"] = "ratio_below_threshold_and_consecutive_days_met"
    output_payload["recommend_action"] = "tighten_social_news_fallback_ratio_to_0_80"
    output_payload["consecutive_days"] = int(consecutive)
    _write_output()
else:
    print(
        f"[hold] trend_recommendation source={source_type} "
        f"ratio={ratio:.6f} latest_ratio={latest_ratio:.6f} consecutive_days={consecutive} "
        f"recommend_ratio={recommend_ratio:.6f}"
    )
    output_payload["status"] = "hold"
    output_payload["reason"] = "ratio_not_stable_below_threshold"
    output_payload["recommend_action"] = "none"
    output_payload["consecutive_days"] = int(consecutive)
    _write_output()
raise SystemExit(0)
PY
