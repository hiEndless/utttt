import asyncio
import logging
from agent_server.background_main import _run as run_background
from agent_server.final_listen_main import _run as run_final
from agent_server.config import settings


async def _run_all():
    # 并发运行后台任务与 final 监听；退出时需要释放全局资源（如 aiohttp session）
    t1 = asyncio.create_task(run_background(), name="agent_background_main")
    t2 = asyncio.create_task(run_final(), name="final_listen")
    try:
        await asyncio.gather(t1, t2)
    finally:
        # 统一关闭全局 HTTPClient，避免进程退出时报 “Unclosed client session/connector”
        from agent_server.utils.http_client import http_client

        await http_client.close()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
