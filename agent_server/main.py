import asyncio
import logging
from agent_server.background_main import _run as run_background
from agent_server.final_listen_main import _run as run_final
from agent_server.config import settings


async def _run_all():
    t1 = asyncio.create_task(run_background(), name="agent_background_main")
    t2 = asyncio.create_task(run_final(), name="final_listen")
    await asyncio.gather(t1, t2)


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run_all())


if __name__ == "__main__":
    main()
