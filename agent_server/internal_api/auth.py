from fastapi import Header, HTTPException, status

from agent_server.config import settings


def verify_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> bool:
    # 中文注释：内部接口默认启用 header 鉴权；若未配置 token，则放行（便于本地开发）。
    expected = str(getattr(settings, "internal_agent_token", "") or "").strip()
    if not expected:
        return True
    provided = str(x_internal_token or "").strip()
    if not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )
    return True

