from __future__ import annotations

import logging
import os

import uvicorn

from services.agent_server_new.app.http_app import create_app


app = create_app()


def main() -> None:
    log_level = str(os.getenv("AGENT_SERVICE_LOG_LEVEL", "info")).lower()
    host = str(os.getenv("AGENT_SERVICE_HOST", "127.0.0.1") or "127.0.0.1")
    port = int(str(os.getenv("AGENT_SERVICE_PORT", "9971") or "9971"))
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger("agent_server_new").info("启动 agent_server_new HTTP 服务，监听 %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()

