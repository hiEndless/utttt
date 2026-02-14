import logging

import uvicorn

from agent_server.config import settings
from agent_server.internal_api.app import create_app


app = create_app()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    uvicorn.run(
        app,
        host=getattr(settings, "internal_agent_api_host", "127.0.0.1"),
        port=int(getattr(settings, "internal_agent_api_port", 9941)),
        log_level=str(getattr(settings, "log_level", "info")).lower(),
    )


if __name__ == "__main__":
    main()

