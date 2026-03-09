from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, Optional, Sequence

from agent_server_new.app import create_trade_event_workflow_from_env
from agent_server_new.app.workflows.trade_event_workflow import TradeEventInput


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="agent_server_new 最小运行入口")
    p.add_argument("--dry-run", action="store_true", help="仅初始化 workflow，不执行推理")
    p.add_argument("--event-id", default="manual-evt-001", help="事件 ID")
    p.add_argument("--exchange", default="binance", help="交易所")
    p.add_argument("--symbol", default="ETHUSDT", help="交易对")
    p.add_argument("--signal-direction", default="long", help="信号方向: long/short")
    p.add_argument("--payload-json", default='{"event_type":"manual_signal"}', help="事件 payload(JSON)")
    return p


def _parse_payload(raw: str) -> Dict[str, Any]:
    try:
        obj = json.loads(str(raw or "{}"))
    except Exception:
        obj = {}
    return obj if isinstance(obj, dict) else {}


async def _run_once(
    *,
    event_id: str,
    exchange: str,
    symbol: str,
    signal_direction: str,
    payload: Dict[str, Any],
) -> int:
    wf = create_trade_event_workflow_from_env()
    event = TradeEventInput(
        event_id=event_id,
        exchange=exchange,
        symbol=symbol,
        signal_direction=signal_direction,
        payload=payload,
    )
    plan = await wf.run(event)
    print(f"执行完成: action={plan.action} direction={plan.direction} notes={plan.notes}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    wf = create_trade_event_workflow_from_env()
    if args.dry_run:
        print(f"初始化成功: workflow={wf.__class__.__name__} exchange={args.exchange} symbol={args.symbol}")
        return 0

    payload = _parse_payload(args.payload_json)
    return asyncio.run(
        _run_once(
            event_id=str(args.event_id),
            exchange=str(args.exchange),
            symbol=str(args.symbol),
            signal_direction=str(args.signal_direction),
            payload=payload,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

