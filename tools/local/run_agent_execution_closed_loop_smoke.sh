#!/usr/bin/env bash
set -euo pipefail

EVENT_TYPE="indicator_signal"
SIGNAL_DIRECTION="long"
EXCHANGE="binance"
SYMBOL="ETHUSDT"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_execution_closed_loop_smoke.sh [options]

Options:
  --event-type <type>          事件类型（默认 indicator_signal）
  --signal-direction <dir>     信号方向（默认 long）
  --exchange <name>            交易所（默认 binance）
  --symbol <name>              交易对（默认 ETHUSDT）
  --help, -h                   显示帮助

Description:
  运行最小 agent->execution 闭环 smoke（固定 stub provider），输出：
  signal_verdict/signal_direction/execution_action/reject_reason。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --event-type)
      EVENT_TYPE="${2:-$EVENT_TYPE}"
      shift 2
      ;;
    --signal-direction)
      SIGNAL_DIRECTION="${2:-$SIGNAL_DIRECTION}"
      shift 2
      ;;
    --exchange)
      EXCHANGE="${2:-$EXCHANGE}"
      shift 2
      ;;
    --symbol)
      SYMBOL="${2:-$SYMBOL}"
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

"$PY_BIN" - "$EVENT_TYPE" "$SIGNAL_DIRECTION" "$EXCHANGE" "$SYMBOL" <<'PY'
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from services.agent_server_new.domain.contracts import Confidence, SignalVerdict
from services.agent_server_new.domain.signal_decision_agent import SignalDecisionEvalResult
from services.agent_server_new.ports.market_state import MarketStateSnapshot


if len(sys.argv) != 5:
    raise SystemExit("usage: <event_type> <signal_direction> <exchange> <symbol>")

event_type, signal_direction, exchange, symbol = [str(x) for x in sys.argv[1:5]]


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
        "summary": "smoke",
    }


class _MarketState:
    async def get_market_state(self, ex: str, sym: str):
        return MarketStateSnapshot(
            exchange=ex,
            symbol=sym,
            msl=_build_msl_from_dict(_sample_msl(sym)),
            msl_meta={"schema_version": 2, "inference_version": "smoke"},
            cross_horizon={"alignment": "aligned", "suggested_policy": "follow_long_term", "policy_reason": "smoke"},
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


class _SignalDecisionAgent:
    def decide(self, **kwargs):  # noqa: ANN003
        _ = kwargs
        return SignalDecisionEvalResult(
            signal=SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.8)),
            decision_agent_key="technical",
            decision_mode="rule",
            llm_parse_status="rule_only",
        )


class _ExecutionDecider:
    async def decide(self, payload):  # noqa: ANN001
        _ = payload
        return {"execution_action": "hold", "reject_reason": "risk_limit_blocked"}


async def _run() -> dict:
    wf = TradeEventWorkflow(
        market_state=_MarketState(),
        position_context=_Position(),
        active_events=_Events(),
        execution_decider=_ExecutionDecider(),
        recorder=None,
        legacy_pipeline_enabled=False,
        signal_decision_agent=_SignalDecisionAgent(),
    )
    out = await wf.run_with_result(
        TradeEventInput(
            event_id="evt-smoke-closed-loop-001",
            exchange=exchange,
            symbol=symbol,
            signal_direction=signal_direction,
            payload={"event_type": event_type},
        )
    )
    execution_result = dict(out.execution_result or {})
    return {
        "event_id": "evt-smoke-closed-loop-001",
        "exchange": exchange,
        "symbol": symbol,
        "signal_verdict": str(out.signal_decision.signal_verdict),
        "signal_direction": str(out.signal_decision.signal_direction),
        "decision_agent_key": str(out.signal_decision.decision_agent_key),
        "execution_action": str(execution_result.get("execution_action") or ""),
        "reject_reason": str(execution_result.get("reject_reason") or ""),
        "signal_decision": asdict(out.signal_decision),
    }


print(json.dumps(asyncio.run(_run()), ensure_ascii=False))
PY

