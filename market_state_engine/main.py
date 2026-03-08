from __future__ import annotations

import logging
import os

import uvicorn

from market_state_engine.app import create_app


app = create_app()


def main() -> None:
    log_level = str(os.getenv("MARKET_STATE_ENGINE_LOG_LEVEL", "info")).lower()
    host = str(os.getenv("MARKET_STATE_ENGINE_HOST", "127.0.0.1"))
    port = int(os.getenv("MARKET_STATE_ENGINE_PORT", "9951"))
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    uvicorn.run(app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
