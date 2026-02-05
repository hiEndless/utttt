import redis
import json
import os
from agent_server.config import settings as cfg


def _read_json_list(client, key: str):
    try:
        v = client.get(key)
        return json.loads(v) if v else []
    except Exception:
        return []


# 中文注释：复用同步 Redis 客户端，避免每次调用都新建连接池导致连接数暴涨
_SYNC_CLIENT: redis.Redis | None = None


def _get_sync_client() -> redis.Redis:
    global _SYNC_CLIENT
    if _SYNC_CLIENT is not None:
        return _SYNC_CLIENT
    password = cfg.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", 10))
    pool = redis.ConnectionPool(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        password=(password or None),
        decode_responses=True,
        max_connections=max_connections,
    )
    _SYNC_CLIENT = redis.Redis(connection_pool=pool)
    return _SYNC_CLIENT


def get_position(exchange: str, symbol: str) -> list[dict]:
    client = _get_sync_client()
    key = f"positions:{exchange}"
    data = _read_json_list(client, key)
    filtered = [p for p in (data or []) if isinstance(p, dict) and str(p.get("symbol")) == symbol]
    out = []
    for p in filtered:
        out.append(
            {
                "symbol": p.get("symbol"),
                "position_side": p.get("positionSide"),
                "size": p.get("positionAmt"),
                "notional": p.get("notional"),
                "pnl_ratio": p.get("pnl_ratio"),
                "open_time": p.get("open_time"),
                "trade_id": p.get("trade_id"),
                "initialMargin": p.get("initialMargin")  # 占用保证金
            }
        )
    return out


if __name__ == "__main__":
    print(get_position("binance", "ETHUSDT"))
