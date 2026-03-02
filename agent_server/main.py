import asyncio
import logging
import signal
from agent_server.config import settings
from agent_server.supervisor import AgentServiceSupervisor


async def _run_all():
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

    supervisor = AgentServiceSupervisor(stop_event=stop_event)
    await supervisor.bootstrap()
    try:
        await stop_event.wait()
    finally:
        await supervisor.shutdown()
        # 统一关闭全局 HTTPClient，避免进程退出时报 “Unclosed client session/connector”
        from agent_server.utils.http_client import http_client

        await http_client.close()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
