import redis
import json
from event_center.config import cfg

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]

_REDIS_CLIENT = None


def get_redis_client() -> redis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        # 复用单例客户端/连接池，避免高频创建导致 Redis 连接数暴涨
        _REDIS_CLIENT = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=(cfg.redis_password or None),
            decode_responses=True,
        )
    return _REDIS_CLIENT


def _read_json(client, key: str):
    try:
        val = client.get(key)
        return json.loads(val) if val else {}
    except Exception:
        return {}


def load_all_indicators(symbol: str, exchange: str = "binance", client: redis.Redis | None = None) -> dict:
    """
    从 Redis 读取全周期、全指标（当前与上一时刻），结构：
    {
      "1m": {
        "ema": {..., "prev": {...}},
        "macd": {..., "prev": {...}},
        ...
      },
      ...
    }
    """
    client = client or get_redis_client()
    out = {}
    ex = exchange
    for iv in INTERVALS:
        cur_key = f"indicators:{ex}:{symbol}:{iv}"
        prev_key = f"indicators:prev:{ex}:{symbol}:{iv}"
        cur = _read_json(client, cur_key)
        prev = _read_json(client, prev_key)
        merged = {}
        for k, v in (cur or {}).items():
            merged[k] = dict(v or {})
            if isinstance(prev, dict) and k in prev:
                merged[k]["prev"] = prev.get(k)
        out[iv] = merged
    return out


if __name__ == "__main__":
    indicators = load_all_indicators("BTCUSDT", "binance")
    print(json.dumps(indicators, ensure_ascii=False))
