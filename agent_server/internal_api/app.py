from __future__ import annotations

from fastapi import FastAPI

from agent_server.internal_api.routes import router


def create_app() -> FastAPI:
    # 中文注释：内部接口不对外暴露文档，避免误用；如需可临时打开 docs_url。
    app = FastAPI(
        title="agent_server_internal_api",
        docs_url="/docs",
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(router)
    return app

