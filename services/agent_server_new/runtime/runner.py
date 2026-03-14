from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict, Optional, Sequence

from services.agent_server_new.app import create_trade_event_workflow_from_env
from services.agent_server_new.app.workflows.trade_event_workflow import TradeEventInput


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="agent_server_new 最小运行入口")
    p.add_argument("--dry-run", action="store_true", help="仅初始化 workflow，不执行推理")
    p.add_argument("--event-id", default="manual-evt-001", help="事件 ID")
    p.add_argument("--exchange", default="binance", help="交易所")
    p.add_argument("--symbol", default="ETHUSDT", help="交易对")
    p.add_argument("--signal-direction", default="long", help="信号方向: long/short")
    p.add_argument("--payload-json", default='{"event_type":"manual_signal"}', help="事件 payload(JSON)")
    p.add_argument(
        "--use-execution-result",
        action="store_true",
        help="优先输出 execution_service 最终动作（若 workflow 已接 execution_decider）",
    )
    p.add_argument("--print-json", action="store_true", help="以 JSON 输出执行结果，便于脚本消费")
    p.add_argument(
        "--fail-on-execution-reject",
        action="store_true",
        help="当 execution 返回 reject_reason 时以非 0 退出（便于任务编排）",
    )
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
    use_execution_result: bool,
    print_json: bool,
    fail_on_execution_reject: bool,
) -> int:
    wf = create_trade_event_workflow_from_env()
    event = TradeEventInput(
        event_id=event_id,
        exchange=exchange,
        symbol=symbol,
        signal_direction=signal_direction,
        payload=payload,
    )
    if use_execution_result and hasattr(wf, "run_with_result"):
        out = await wf.run_with_result(event)  # type: ignore[attr-defined]
        if out.execution_result is not None:
            action = str(out.execution_result.get("execution_action") or "unknown")
            reason = str(out.execution_result.get("reject_reason") or "")
            result = {
                "source": "execution",
                "action": action,
                "reason": reason,
                "notes": str(out.agent_plan.notes or ""),
            }
            if print_json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"执行完成[execution]: action={action} reason={reason} notes={out.agent_plan.notes}")
            if fail_on_execution_reject and reason:
                return 2
            return 0
        plan = out.agent_plan
        result = {
            "source": "agent_fallback",
            "action": str(plan.action),
            "direction": str(plan.direction),
            "notes": str(plan.notes or ""),
        }
        if print_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"执行完成[agent-fallback]: action={plan.action} direction={plan.direction} notes={plan.notes}")
        return 0

    plan = await wf.run(event)
    result = {
        "source": "agent",
        "action": str(plan.action),
        "direction": str(plan.direction),
        "notes": str(plan.notes or ""),
    }
    if print_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"执行完成[agent]: action={plan.action} direction={plan.direction} notes={plan.notes}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    wf = create_trade_event_workflow_from_env()
    if args.dry_run:
        print(f"初始化成功: workflow={wf.__class__.__name__} exchange={args.exchange} symbol={args.symbol}")
        return 0
    runtime_profile = str(os.getenv("AGENT_RUNTIME_PROFILE", "dev") or "dev").strip().lower()
    if runtime_profile in {"prod", "production"} and not bool(args.use_execution_result):
        print("运行失败: production profile requires --use-execution-result")
        return 2

    payload = _parse_payload(args.payload_json)
    return asyncio.run(
        _run_once(
            event_id=str(args.event_id),
            exchange=str(args.exchange),
            symbol=str(args.symbol),
            signal_direction=str(args.signal_direction),
            payload=payload,
            use_execution_result=bool(args.use_execution_result),
            print_json=bool(args.print_json),
            fail_on_execution_reject=bool(args.fail_on_execution_reject),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
