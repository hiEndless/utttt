#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_agent_signal_decision_source_quality_guard.sh [report_json] [min_source_count] [min_market_indicator_llm_ok_ratio] [min_onchain_wallet_llm_ok_ratio] [min_large_liquidation_llm_ok_ratio] [min_social_news_llm_ok_ratio] [min_global_decision_mode_llm_ratio] [min_global_llm_ok_ratio]

Description:
  读取 signal_decision_replay 报告，按来源检查 llm_ok 占比是否达到下限阈值。
  当某来源样本数小于 min_source_count 时，打印 [skip] 并不阻断。

Args:
  report_json                          报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  min_source_count                     每来源最小样本数（默认 10）
  min_market_indicator_llm_ok_ratio    market_indicator 的 llm_ok 比例下限（默认 -1 忽略）
  min_onchain_wallet_llm_ok_ratio      onchain_wallet 的 llm_ok 比例下限（默认 -1 忽略）
  min_large_liquidation_llm_ok_ratio   large_liquidation 的 llm_ok 比例下限（默认 -1 忽略）
  min_social_news_llm_ok_ratio         social_news 的 llm_ok 比例下限（默认 -1 忽略）
  min_global_decision_mode_llm_ratio   全局 decision_mode=llm 比例下限（默认 -1 忽略）
  min_global_llm_ok_ratio              全局 llm_ok 比例下限（默认 -1 忽略）

Failure Codes:
  exit 1  任一来源 llm_ok 比例低于阈值（阻断）
  exit 2  输入文件缺失或不可读
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

REPORT_PATH="${1:-verification/reports/agent_signal_decision_replay.latest.json}"
MIN_SOURCE_COUNT_RAW="${2:-10}"
MIN_MARKET_INDICATOR_RATIO_RAW="${3:--1}"
MIN_ONCHAIN_WALLET_RATIO_RAW="${4:--1}"
MIN_LARGE_LIQUIDATION_RATIO_RAW="${5:--1}"
MIN_SOCIAL_NEWS_RATIO_RAW="${6:--1}"
MIN_GLOBAL_DECISION_MODE_LLM_RATIO_RAW="${7:--1}"
MIN_GLOBAL_LLM_OK_RATIO_RAW="${8:--1}"

if ! test -r "$REPORT_PATH"; then
  echo "[failed] signal decision replay report not readable: $REPORT_PATH"
  exit 2
fi

"$PY_BIN" - <<'PY' "$REPORT_PATH" "$MIN_SOURCE_COUNT_RAW" "$MIN_MARKET_INDICATOR_RATIO_RAW" "$MIN_ONCHAIN_WALLET_RATIO_RAW" "$MIN_LARGE_LIQUIDATION_RATIO_RAW" "$MIN_SOCIAL_NEWS_RATIO_RAW" "$MIN_GLOBAL_DECISION_MODE_LLM_RATIO_RAW" "$MIN_GLOBAL_LLM_OK_RATIO_RAW"
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

report_path = Path(sys.argv[1])
min_source_count_raw = str(sys.argv[2] or "10").strip()
min_market_indicator_ratio_raw = str(sys.argv[3] or "-1").strip()
min_onchain_wallet_ratio_raw = str(sys.argv[4] or "-1").strip()
min_large_liquidation_ratio_raw = str(sys.argv[5] or "-1").strip()
min_social_news_ratio_raw = str(sys.argv[6] or "-1").strip()
min_global_decision_mode_llm_ratio_raw = str(sys.argv[7] or "-1").strip()
min_global_llm_ok_ratio_raw = str(sys.argv[8] or "-1").strip()


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


min_source_count = max(1, _to_int(min_source_count_raw, 10))
thresholds = {
    "market_indicator": _to_float(min_market_indicator_ratio_raw, -1.0),
    "onchain_wallet": _to_float(min_onchain_wallet_ratio_raw, -1.0),
    "large_liquidation": _to_float(min_large_liquidation_ratio_raw, -1.0),
    "social_news": _to_float(min_social_news_ratio_raw, -1.0),
}
min_global_decision_mode_llm_ratio = _to_float(min_global_decision_mode_llm_ratio_raw, -1.0)
min_global_llm_ok_ratio = _to_float(min_global_llm_ok_ratio_raw, -1.0)

if max([*thresholds.values(), min_global_decision_mode_llm_ratio, min_global_llm_ok_ratio]) < 0:
    print("[skip] signal decision source quality guard disabled (all thresholds < 0)")
    raise SystemExit(0)

try:
    report = json.loads(report_path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"[failed] invalid signal decision replay report json: {report_path} err={exc}")
    raise SystemExit(3)

if not isinstance(report, dict):
    print(f"[failed] invalid signal decision replay report payload type: {report_path}")
    raise SystemExit(3)

schema_version = str(report.get("schema_version") or "").strip()
if schema_version and schema_version != "agent-signal-decision-replay-report-v1":
    print(f"[failed] unsupported signal decision replay schema_version: {schema_version}")
    raise SystemExit(3)

total_counts: dict[str, int] = defaultdict(int)
for row in list(report.get("source_decision_mode_counts") or []):
    if not isinstance(row, dict):
        continue
    src = str(row.get("signal_source_type") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src:
        continue
    total_counts[src] += max(0, cnt)

llm_ok_counts: dict[str, int] = defaultdict(int)
for row in list(report.get("source_llm_parse_status_counts") or []):
    if not isinstance(row, dict):
        continue
    src = str(row.get("signal_source_type") or "").strip().lower()
    status = str(row.get("llm_parse_status") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src or status != "llm_ok":
        continue
    llm_ok_counts[src] += max(0, cnt)

errors: list[str] = []
for src, min_ratio in thresholds.items():
    total = int(total_counts.get(src, 0))
    llm_ok = int(llm_ok_counts.get(src, 0))
    ratio = 0.0 if total <= 0 else float(llm_ok) / float(total)
    if min_ratio < 0:
        print(f"[skip] source={src} threshold disabled")
        continue
    if total < min_source_count:
        print(
            f"[skip] source={src} sample too small "
            f"(total={total} min_source_count={min_source_count})"
        )
        continue
    if ratio < min_ratio:
        errors.append(
            f"source={src} llm_ok_ratio={ratio:.6f} "
            f"< min_ratio={min_ratio:.6f} total={total} llm_ok={llm_ok}"
        )
    else:
        print(
            f"[passed] source={src} llm_ok_ratio={ratio:.6f} "
            f"min_ratio={min_ratio:.6f} total={total} llm_ok={llm_ok}"
        )

decision_mode_llm_count = 0
decision_mode_rows = list(report.get("decision_mode_counts") or [])
if not decision_mode_rows:
    source_mode_rows = list(report.get("source_decision_mode_counts") or [])
    aggregated_mode_counts: dict[str, int] = defaultdict(int)
    for row in source_mode_rows:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("decision_mode") or "").strip().lower()
        if not mode:
            continue
        aggregated_mode_counts[mode] += max(0, int(row.get("count") or 0))
    decision_mode_rows = [
        {"decision_mode": key, "count": value} for key, value in aggregated_mode_counts.items()
    ]

for row in decision_mode_rows:
    if not isinstance(row, dict):
        continue
    mode = str(row.get("decision_mode") or "").strip().lower()
    if mode != "llm":
        continue
    decision_mode_llm_count += max(0, int(row.get("count") or 0))

global_total = int(sum(total_counts.values()))
global_llm_ok = int(sum(llm_ok_counts.values()))
global_decision_mode_llm_ratio = 0.0 if global_total <= 0 else float(decision_mode_llm_count) / float(global_total)
global_llm_ok_ratio = 0.0 if global_total <= 0 else float(global_llm_ok) / float(global_total)

if min_global_decision_mode_llm_ratio >= 0:
    if global_decision_mode_llm_ratio < min_global_decision_mode_llm_ratio:
        errors.append(
            f"global decision_mode_llm_ratio={global_decision_mode_llm_ratio:.6f} "
            f"< min_ratio={min_global_decision_mode_llm_ratio:.6f} total={global_total} decision_mode_llm={decision_mode_llm_count}"
        )
    else:
        print(
            f"[passed] global decision_mode_llm_ratio={global_decision_mode_llm_ratio:.6f} "
            f"min_ratio={min_global_decision_mode_llm_ratio:.6f} total={global_total} decision_mode_llm={decision_mode_llm_count}"
        )
else:
    print("[skip] global decision_mode_llm_ratio threshold disabled")

if min_global_llm_ok_ratio >= 0:
    if global_llm_ok_ratio < min_global_llm_ok_ratio:
        errors.append(
            f"global llm_ok_ratio={global_llm_ok_ratio:.6f} "
            f"< min_ratio={min_global_llm_ok_ratio:.6f} total={global_total} llm_ok={global_llm_ok}"
        )
    else:
        print(
            f"[passed] global llm_ok_ratio={global_llm_ok_ratio:.6f} "
            f"min_ratio={min_global_llm_ok_ratio:.6f} total={global_total} llm_ok={global_llm_ok}"
        )
else:
    print("[skip] global llm_ok_ratio threshold disabled")

if errors:
    print("[failed] signal decision source quality guard")
    for item in errors:
        print(f"- {item}")
    raise SystemExit(1)

print("[passed] signal decision source quality guard all enabled source thresholds satisfied")
PY
