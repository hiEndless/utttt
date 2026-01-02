"""
事件流 + Reducer
"""

import asyncio
import logging
import signal
from agent_server.reducers.temporal_state import TemporalStateReducer
from agent_server.config import settings


async def _run():
    reducer = TemporalStateReducer()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logging.getLogger("temporal").info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)
    task = asyncio.create_task(reducer.run(), name="temporal_state_reducer")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        try:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            pass


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
