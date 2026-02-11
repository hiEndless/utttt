import asyncio
import logging
import signal
from agent_server.background_main import _run as run_background
from agent_server.final_listen_main import _run as run_final
from agent_server.risk.risk_state_cron import _run as run_risk_cron
from agent_server.config import settings


async def _run_all():
    # 并发运行后台任务、final 监听以及风控定时任务；退出时需要释放全局资源（如 aiohttp session）
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_sig(*_):
        logging.info("Main received stop signal, stopping all services...")
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        # Windows or non-main thread might not support signal handlers
        logging.warning("Signal handlers not supported in this environment.")

    t1 = asyncio.create_task(run_background(stop_event), name="agent_background_main")
    t2 = asyncio.create_task(run_final(stop_event), name="final_listen")
    t3 = asyncio.create_task(run_risk_cron(stop_event), name="risk_state_cron")
    try:
        await asyncio.gather(t1, t2, t3)
    finally:
        # 统一关闭全局 HTTPClient，避免进程退出时报 “Unclosed client session/connector”
        from agent_server.utils.http_client import http_client

        await http_client.close()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
