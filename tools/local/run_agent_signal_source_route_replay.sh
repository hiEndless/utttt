#!/usr/bin/env bash
set -euo pipefail

EXCHANGE="binance"
SYMBOL="ETHUSDT"
FORMAT="table"
OUTPUT_PATH=""

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_signal_source_route_replay.sh [options]

Options:
  --exchange <name>  交易所（默认 binance）
  --symbol <name>    交易对（默认 ETHUSDT）
  --format <type>    输出格式（table|json，默认 table）
  --output <path>    输出文件路径（仅 format=json 时生效）
  --help, -h         显示帮助

Description:
  运行最小业务路由回放（4类来源）：
  market_indicator/onchain_wallet/large_liquidation/social_news
  输出每个样例的 signal_source_type -> decision_agent_key -> execution_action，
  若任一样例路由不匹配预期则返回非0退出码。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --exchange)
      EXCHANGE="${2:-$EXCHANGE}"
      shift 2
      ;;
    --symbol)
      SYMBOL="${2:-$SYMBOL}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-$FORMAT}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-$OUTPUT_PATH}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - "$EXCHANGE" "$SYMBOL" "$FORMAT" "$OUTPUT_PATH" <<'PY'
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.ports.market_state import MarketStateSnapshot

if len(sys.argv) != 5:
    raise SystemExit("usage: <exchange> <symbol> <format> <output_path>")

exchange = str(sys.argv[1] or "binance").strip() or "binance"
symbol = str(sys.argv[2] or "ETHUSDT").strip() or "ETHUSDT"
output_format = str(sys.argv[3] or "table").strip().lower()
output_path = str(sys.argv[4] or "").strip()
if output_format not in {"table", "json"}:
    raise SystemExit("[failed] --format must be one of: table|json")
if output_path and output_format != "json":
    raise SystemExit("[failed] --output requires --format json")


def _sample_msl(sym: str) -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": sym,
        "market_regime": {"trend": "bullish", "phase": "continuation", "timeframe_alignment": "aligned", "strength": 0.72},
        "liquidity_state": {"dominant_pressure": "buyers", "liquidity_risk": "neutral", "orderbook_bias": "neutral", "liquidation_proximity": "none"},
        "positioning_state": {"crowding": "balanced", "whale_bias": "unknown", "retail_bias": "unknown", "oi_trend": "expanding"},
        "volatility_state": {"volatility_regime": "normal", "expansion_risk": "unknown", "volatility_direction": "upside"},
        "market_risk_state": {"cascade_risk": "low", "squeeze_probability": "low", "reversal_risk": "low"},
        "market_structure_state": {"support_strength": "unknown", "resistance_strength": "unknown", "range_state": "breakout", "trend_structure": "hh_hl"},
        "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
        "anomalies": [],
        "summary": "route_replay",
    }


class _MarketState:
    async def get_market_state(self, ex: str, sym: str):
        return MarketStateSnapshot(
            exchange=ex,
            symbol=sym,
            msl=_build_msl_from_dict(_sample_msl(sym)),
            msl_meta={"schema_version": 2, "inference_version": "route_replay"},
            cross_horizon={"alignment": "aligned", "suggested_policy": "follow_long_term", "policy_reason": "route_replay"},
            state_features={"evidence": {}, "anomalies": {}},
        )


class _Position:
    async def get_position_context(self, ex: str, sym: str):
        _ = (ex, sym)
        return {"has_position": False}


class _Events:
    async def get_active_events(self, ex: str, sym: str):
        _ = (ex, sym)
        return []


class _ExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        risk_hints = dict((payload or {}).get("risk_hints") or {})
        action_hint = str(risk_hints.get("agent_action_hint") or "").strip().lower()
        if action_hint == "add":
            return {"execution_action": "add", "reject_reason": None}
        return {"execution_action": "hold", "reject_reason": "route_replay_hold"}


async def _run() -> tuple[list[dict[str, object]], bool]:
    wf = TradeEventWorkflow(
        market_state=_MarketState(),
        position_context=_Position(),
        active_events=_Events(),
        execution_decider=_ExecutionDecider(),
        recorder=None,
        legacy_pipeline_enabled=False,
    )
    cases = [
        ("market_indicator", "technical"),
        ("onchain_wallet", "onchain"),
        ("large_liquidation", "liquidation"),
        ("social_news", "social_news"),
    ]
    rows: list[dict[str, object]] = []
    success = True
    for idx, (source_type, expected_agent_key) in enumerate(cases, start=1):
        event_id = f"evt-route-replay-{idx:03d}"
        out = await wf.run_with_result(
            TradeEventInput(
                event_id=event_id,
                exchange=exchange,
                symbol=symbol,
                signal_direction="long",
                payload={
                    "event_type": "xfeed_unknown_source_type",
                    "signal_source_type": source_type,
                },
            )
        )
        actual_agent_key = str(out.signal_decision.decision_agent_key or "")
        execution_action = str((out.execution_result or {}).get("execution_action") or "")
        row = {
            "event_id": event_id,
            "signal_source_type": source_type,
            "expected_agent_key": expected_agent_key,
            "decision_agent_key": actual_agent_key,
            "signal_verdict": str(out.signal_decision.signal_verdict),
            "signal_direction": str(out.signal_decision.signal_direction),
            "execution_action": execution_action,
            "route_match": actual_agent_key == expected_agent_key,
        }
        rows.append(row)
        if actual_agent_key != expected_agent_key:
            success = False
    return rows, success


rows, ok = asyncio.run(_run())
result = {
    "schema_version": "agent-signal-source-route-replay-v1",
    "exchange": exchange,
    "symbol": symbol,
    "count": len(rows),
    "ok": bool(ok),
    "rows": rows,
}

if output_format == "json":
    rendered = json.dumps(result, ensure_ascii=False)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print(f"[ok] wrote {out}")
    print(rendered)
else:
    print(
        "event_id\tsignal_source_type\texpected_agent_key\tdecision_agent_key\t"
        "signal_verdict\tsignal_direction\texecution_action\troute_match"
    )
    for row in rows:
        print(
            f"{str(row.get('event_id') or '')}\t"
            f"{str(row.get('signal_source_type') or '')}\t"
            f"{str(row.get('expected_agent_key') or '')}\t"
            f"{str(row.get('decision_agent_key') or '')}\t"
            f"{str(row.get('signal_verdict') or '')}\t"
            f"{str(row.get('signal_direction') or '')}\t"
            f"{str(row.get('execution_action') or '')}\t"
            f"{str(row.get('route_match') or False)}"
        )
if not ok:
    raise SystemExit(1)
PY
