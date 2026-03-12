from __future__ import annotations

import logging
import os

import uvicorn

from services.execution_service.app import create_app


app = create_app()


def main() -> None:
    log_level = str(os.getenv("EXECUTION_SERVICE_LOG_LEVEL", "info")).lower()
    host = str(os.getenv("EXECUTION_SERVICE_HOST", "127.0.0.1"))
    port = int(os.getenv("EXECUTION_SERVICE_PORT", "9962"))
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger("execution_service").info("启动 execution_service，监听 %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
