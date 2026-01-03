import redis
import json
from agent_server.config import settings as cfg


def _read_json_list(client, key: str):
    try:
        v = client.get(key)
        return json.loads(v) if v else []
    except Exception:
        return []


def get_position(exchange: str, symbol: str) -> list[dict]:
    client = redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        password=(cfg.redis_password or None),
        decode_responses=True,
    )
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
                "entry_ts": p.get("updateTime"),
                "trade_id": p.get("trade_id"),
            }
        )
    return out


if __name__ == "__main__":
    print(get_position("binance", "1000PEPEUSDT"))
