import asyncio
import logging
import os
from agent_server.background_main import _run as run_background
from agent_server.final_listen_main import _run as run_final_listen
from agent_server.config import settings

# 配置日志
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    # 减少其他 logger 的噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("agno").setLevel(logging.WARNING)
    logging.getLogger("agno.workflow").setLevel(logging.WARNING)
    logging.getLogger("agno.agent").setLevel(logging.WARNING)
    logging.getLogger("agno.models").setLevel(logging.WARNING)


async def _run_all():
    """运行所有 agent 服务：background 和 final_listen"""
    # 启动 background 服务（生成市场背景数据）
    t1 = asyncio.create_task(run_background(), name="agent_background_main")
    
    # 启动 final_listen 服务（监听 final_events）
    t2 = asyncio.create_task(run_final_listen(), name="final_listen")
    
    # 等待所有任务
    await asyncio.gather(t1, t2)


def main():
    setup_logging()
    print("[Main] 启动 Agent Server")
    print("[Main] 包含服务:")
    print("  - background_main: 生成市场背景数据（market_structure, market_state）")
    print("  - final_listen_main: 监听 final_events 并执行信号验证")
    print("[Main] 注意: 如需运行交易决策服务，请使用: python -m agent_server.trade_decision_main")
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
