"""
交易决策服务独立入口点
专门用于监听 L1 事件并执行交易决策
不影响原有的 background 和 final_listen 服务
"""
import asyncio
import logging
import os
from agent_server.trade_listen_main import _run as run_trade_listen
from agent_server.config import settings

# 配置日志，减少噪音
def setup_logging():
    # 设置根 logger 为 WARNING，只显示重要信息
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    # 减少其他 logger 的噪音（将 LLM API 错误降级，这些会被自动重试）
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("agno").setLevel(logging.CRITICAL)  # 只显示致命错误
    logging.getLogger("agno.workflow").setLevel(logging.CRITICAL)
    logging.getLogger("agno.agent").setLevel(logging.CRITICAL)
    logging.getLogger("agno.models").setLevel(logging.CRITICAL)
    logging.getLogger("agno.models.openai").setLevel(logging.CRITICAL)  # LLM API 错误会被重试，不需要显示
    
    # 数据库相关警告改为 ERROR（因为懒加载是正常的）
    logging.getLogger("agent_server.utils.db_utils").setLevel(logging.ERROR)
    logging.getLogger("agent_server.utils.trade_event_recorder").setLevel(logging.ERROR)
    logging.getLogger("agent_server.utils.price_fetcher").setLevel(logging.ERROR)
    
    # trade_decision logger 显示 INFO（handler 已在 trade_listen_main.py 中配置）
    logging.getLogger("trade_decision").setLevel(logging.INFO)


def main():
    setup_logging()
    print("[TradeDecision] 启动交易决策服务")
    print(f"[TradeDecision] 处理模式: 所有币种")
    print(f"[TradeDecision] 日志目录: {os.path.join(os.path.dirname(__file__), 'logs')}")
    print(f"[TradeDecision] 注意: 此服务仅用于交易决策，不影响 background 和 final_listen 服务")
    asyncio.run(run_trade_listen())


if __name__ == "__main__":
    main()

