from __future__ import annotations

import argparse
import asyncio
from typing import Any, Dict, Optional, Sequence

from agent_server_new.adapters.active_events_stub import StubActiveEventsProvider
from agent_server_new.adapters.market_state_http import _build_msl_from_dict
from agent_server_new.adapters.position_context_stub import StubPositionContextProvider
from agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from agent_server_new.ports.market_state import MarketStateSnapshot
from market_state_engine.service import MarketStateService


def _sample_raw_market_structure() -> Dict[str, Any]:
    return {
        "horizons": {
            "fused": {
                "horizons": {
                    "short_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "medium"}}},
                    "mid_term": {
                        "market_background": {
                            "trend_memory": {"price_direction": "up", "price_strength": "strong"},
                            "trend_context": {"label": "trend_continuation"},
                            "volatility_state": "normal",
                        },
                        "participant_background": {"crowding": "normal", "stability": "stable"},
                    },
                    "long_term": {"market_background": {"trend_memory": {"price_direction": "down", "price_strength": "medium"}}},
                }
            }
        },
        "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
    }


class _InMemoryRawStructureProvider:
    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        _ = (exchange, symbol)
        return _sample_raw_market_structure()


class _InProcessMarketStateProvider:
    def __init__(self) -> None:
        self._service = MarketStateService(raw_structure_provider=_InMemoryRawStructureProvider())

    async def get_market_state(self, exchange: str, symbol: str) -> MarketStateSnapshot:
        payload = await self._service.get_market_state(exchange, symbol)
        return MarketStateSnapshot(
            exchange=str(payload.get("exchange") or exchange),
            symbol=str(payload.get("symbol") or symbol),
            msl=_build_msl_from_dict(dict(payload.get("msl") or {})),
            msl_meta=dict(payload.get("msl_meta") or {}),
            msl_bundle=dict(payload.get("msl_bundle") or {}),
            msl_bundle_meta=dict(payload.get("msl_bundle_meta") or {}),
            cross_horizon=dict(payload.get("cross_horizon") or {}),
            state_features=dict(payload.get("state_features") or {}),
            anomaly_flags=[str(x) for x in list(payload.get("anomaly_flags") or []) if x],
            raw_market_structure=dict(payload.get("raw_market_structure") or {}),
        )


async def run_pipeline_once(
    *,
    exchange: str,
    symbol: str,
    signal_direction: str,
    use_execution_result: bool = False,
) -> Dict[str, Any]:
    wf = TradeEventWorkflow(
        market_state=_InProcessMarketStateProvider(),
        position_context=StubPositionContextProvider(),
        active_events=StubActiveEventsProvider(),
        recorder=None,
    )
    event = TradeEventInput(
        event_id="pipeline-smoke-001",
        exchange=exchange,
        symbol=symbol,
        signal_direction=signal_direction,
        payload={"event_type": "manual_signal"},
    )
    if use_execution_result:
        result = await wf.run_with_result(event)
        if result.execution_result is not None:
            return {
                "action": str(result.execution_result.get("execution_action") or "unknown"),
                "direction": str(result.execution_result.get("direction") or result.agent_plan.direction),
                "notes": str(result.execution_result.get("notes") or result.agent_plan.notes),
                "source": "execution",
            }
        out = result.agent_plan
        return {
            "action": out.action,
            "direction": out.direction,
            "notes": out.notes,
            "source": "agent_fallback",
        }
    out = await wf.run(event)
    return {
        "action": out.action,
        "direction": out.direction,
        "notes": out.notes,
        "source": "agent",
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="feature/state/agent 单进程 one-shot smoke")
    p.add_argument("--dry-run", action="store_true", help="仅检查初始化，不执行工作流")
    p.add_argument("--exchange", default="binance")
    p.add_argument("--symbol", default="ETHUSDT")
    p.add_argument("--signal-direction", default="long")
    p.add_argument("--use-execution-result", action="store_true", help="优先输出 execution 最终动作")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    if args.dry_run:
        print(f"初始化完成: exchange={args.exchange} symbol={args.symbol}")
        return 0
    out = asyncio.run(
        run_pipeline_once(
            exchange=str(args.exchange),
            symbol=str(args.symbol),
            signal_direction=str(args.signal_direction),
            use_execution_result=bool(args.use_execution_result),
        )
    )
    print(
        f"one-shot 完成: source={out.get('source','unknown')} "
        f"action={out['action']} direction={out['direction']} notes={out['notes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
