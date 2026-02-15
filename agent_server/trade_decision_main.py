"""
交易决策服务入口 - 监听 l1_events 并执行交易决策
"""

import asyncio
import logging
import os
from agent_server.trade_listen_main import _run as run_trade_listen
from agent_server.config import settings


def setup_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("agno").setLevel(logging.CRITICAL)
    logging.getLogger("trade_decision").setLevel(logging.INFO)
    logging.getLogger("trade_ai_reasoning").setLevel(logging.INFO)


def main():
    setup_logging()
    print("[TradeDecision] 启动交易决策服务")
    print(f"[TradeDecision] 监听流: l1_events")
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    print(f"[TradeDecision] 日志目录: {log_dir}")
    print(f"[TradeDecision] 交易日志: trade_decision_YYYYMMDD.log | AI推理日志: trade_ai_reasoning_YYYYMMDD.log")
    asyncio.run(run_trade_listen())


if __name__ == "__main__":
    main()
