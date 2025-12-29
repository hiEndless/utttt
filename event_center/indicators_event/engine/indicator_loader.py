import redis
import json
from event_center.config import cfg

INTERVALS = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]


def _read_json(client, key: str):
    try:
        val = client.get(key)
        return json.loads(val) if val else {}
    except Exception:
        return {}


def load_all_indicators(symbol: str, exchange: str | None = None) -> dict:
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
    client = redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_db,
        password=(cfg.redis_password or None),
        decode_responses=True,
    )
    out = {}
    ex = (exchange or "binance")
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
    indicators = load_all_indicators("BTCUSDT")
    print(json.dumps(indicators, ensure_ascii=False))
