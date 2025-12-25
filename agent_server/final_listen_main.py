import asyncio
import logging
import signal
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.utils.watchers.final_events import FinalEventsListener


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
    listener = FinalEventsListener(redis)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logging.getLogger("final").info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)
    task = asyncio.create_task(listener.run(), name="final_events_listener")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        try:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            pass
        await redis.close()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
