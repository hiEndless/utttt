#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/local/check_agent_signal_decision_replay_guard.sh [report_json] [min_source_count] [max_market_indicator_ratio] [max_onchain_wallet_ratio] [max_large_liquidation_ratio] [max_social_news_ratio]

Description:
  读取 signal_decision_replay 报告，按来源检查 decision_mode=rule_fallback 占比是否超阈值。
  当某来源样本数小于 min_source_count 时，打印 [skip] 并不阻断。

Args:
  report_json                   报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  min_source_count              每来源最小样本数（默认 10）
  max_market_indicator_ratio    market_indicator 允许最大 rule_fallback 比例（默认 -1 忽略）
  max_onchain_wallet_ratio      onchain_wallet 允许最大 rule_fallback 比例（默认 -1 忽略）
  max_large_liquidation_ratio   large_liquidation 允许最大 rule_fallback 比例（默认 -1 忽略）
  max_social_news_ratio         social_news 允许最大 rule_fallback 比例（默认 -1 忽略）

Failure Codes:
  exit 1  任一来源 rule_fallback 比例超过阈值（阻断）
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
MAX_MARKET_INDICATOR_RATIO_RAW="${3:--1}"
MAX_ONCHAIN_WALLET_RATIO_RAW="${4:--1}"
MAX_LARGE_LIQUIDATION_RATIO_RAW="${5:--1}"
MAX_SOCIAL_NEWS_RATIO_RAW="${6:--1}"

if ! test -r "$REPORT_PATH"; then
  echo "[failed] signal decision replay report not readable: $REPORT_PATH"
  exit 2
fi

"$PY_BIN" - <<'PY' "$REPORT_PATH" "$MIN_SOURCE_COUNT_RAW" "$MAX_MARKET_INDICATOR_RATIO_RAW" "$MAX_ONCHAIN_WALLET_RATIO_RAW" "$MAX_LARGE_LIQUIDATION_RATIO_RAW" "$MAX_SOCIAL_NEWS_RATIO_RAW"
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

report_path = Path(sys.argv[1])
min_source_count_raw = str(sys.argv[2] or "10").strip()
max_market_indicator_ratio_raw = str(sys.argv[3] or "-1").strip()
max_onchain_wallet_ratio_raw = str(sys.argv[4] or "-1").strip()
max_large_liquidation_ratio_raw = str(sys.argv[5] or "-1").strip()
max_social_news_ratio_raw = str(sys.argv[6] or "-1").strip()


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
    "market_indicator": _to_float(max_market_indicator_ratio_raw, -1.0),
    "onchain_wallet": _to_float(max_onchain_wallet_ratio_raw, -1.0),
    "large_liquidation": _to_float(max_large_liquidation_ratio_raw, -1.0),
    "social_news": _to_float(max_social_news_ratio_raw, -1.0),
}

if max(thresholds.values()) < 0:
    print("[skip] signal decision replay guard disabled (all thresholds < 0)")
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

matrix = [dict(x) for x in list(report.get("source_decision_mode_counts") or []) if isinstance(x, dict)]
counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
for row in matrix:
    src = str(row.get("signal_source_type") or "").strip().lower()
    mode = str(row.get("decision_mode") or "").strip().lower()
    cnt = int(row.get("count") or 0)
    if not src:
        continue
    counts[src][mode] += max(0, cnt)

errors: list[str] = []
for src, max_ratio in thresholds.items():
    total = int(sum(counts.get(src, {}).values()))
    fallback = int(counts.get(src, {}).get("rule_fallback", 0))
    ratio = 0.0 if total <= 0 else float(fallback) / float(total)
    if max_ratio < 0:
        print(f"[skip] source={src} threshold disabled")
        continue
    if total < min_source_count:
        print(
            f"[skip] source={src} sample too small "
            f"(total={total} min_source_count={min_source_count})"
        )
        continue
    if ratio > max_ratio:
        errors.append(
            f"source={src} rule_fallback_ratio={ratio:.6f} "
            f"> max_ratio={max_ratio:.6f} total={total} fallback={fallback}"
        )
    else:
        print(
            f"[passed] source={src} rule_fallback_ratio={ratio:.6f} "
            f"max_ratio={max_ratio:.6f} total={total} fallback={fallback}"
        )

if errors:
    print("[failed] signal decision replay guard")
    for item in errors:
        print(f"- {item}")
    raise SystemExit(1)

print("[passed] signal decision replay guard all enabled source thresholds satisfied")
PY
