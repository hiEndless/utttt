import redis
import json
import os
from event_center.config import cfg
from data_server.binance.rest_binance.app.signals.aggregate import compute_all_indicators

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


def _read_json_first_hit(client, keys: list[str]) -> tuple[dict, str | None]:
    for k in keys:
        data = _read_json(client, k)
        if isinstance(data, dict) and data:
            return data, k
    return {}, None


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
    debug = os.getenv("ENGINE_DEBUG", "").lower() in ("1", "true", "yes", "on")
    for iv in INTERVALS:
        # 兼容不同写入命名：symbol 大小写、固定 binance 前缀
        cur_candidates = [
            f"indicators:{ex}:{symbol}:{iv}",
            f"indicators:{ex}:{str(symbol).upper()}:{iv}",
            f"indicators:{ex}:{str(symbol).lower()}:{iv}",
            f"indicators:binance:{symbol}:{iv}",
            f"indicators:binance:{str(symbol).upper()}:{iv}",
            f"indicators:binance:{str(symbol).lower()}:{iv}",
        ]
        prev_candidates = [
            f"indicators:prev:{ex}:{symbol}:{iv}",
            f"indicators:prev:{ex}:{str(symbol).upper()}:{iv}",
            f"indicators:prev:{ex}:{str(symbol).lower()}:{iv}",
            f"indicators:prev:binance:{symbol}:{iv}",
            f"indicators:prev:binance:{str(symbol).upper()}:{iv}",
            f"indicators:prev:binance:{str(symbol).lower()}:{iv}",
        ]

        cur, cur_hit = _read_json_first_hit(client, cur_candidates)
        prev, prev_hit = _read_json_first_hit(client, prev_candidates)

        # Redis 没有指标时，兜底从 klines 现算一次，避免全空导致 signal_strength 恒为 0
        if not cur:
            for kline_key in [
                f"klines:{ex}:{symbol}:{iv}",
                f"klines:{ex}:{str(symbol).upper()}:{iv}",
                f"klines:{ex}:{str(symbol).lower()}:{iv}",
                f"klines:binance:{symbol}:{iv}",
                f"klines:binance:{str(symbol).upper()}:{iv}",
                f"klines:binance:{str(symbol).lower()}:{iv}",
            ]:
                kl = _read_json(client, kline_key)
                if isinstance(kl, list) and len(kl) >= 20:
                    try:
                        cur = compute_all_indicators(kl)
                        cur_hit = f"{kline_key} (computed)"
                    except Exception:
                        cur = {}
                    if cur:
                        break
        if not prev:
            for kline_key in [
                f"klines:{ex}:{symbol}:{iv}",
                f"klines:{ex}:{str(symbol).upper()}:{iv}",
                f"klines:{ex}:{str(symbol).lower()}:{iv}",
                f"klines:binance:{symbol}:{iv}",
                f"klines:binance:{str(symbol).upper()}:{iv}",
                f"klines:binance:{str(symbol).lower()}:{iv}",
            ]:
                kl = _read_json(client, kline_key)
                if isinstance(kl, list) and len(kl) >= 21:
                    try:
                        prev = compute_all_indicators(kl[:-1])
                        prev_hit = f"{kline_key}[:-1] (computed)"
                    except Exception:
                        prev = {}
                    if prev:
                        break

        merged = {}
        for k, v in (cur or {}).items():
            merged[k] = dict(v or {})
            if isinstance(prev, dict) and k in prev:
                merged[k]["prev"] = prev.get(k)
        out[iv] = merged
        if debug:
            print(
                f"[IND_LOADER_DEBUG] symbol={symbol} tf={iv} "
                f"cur_hit={cur_hit or '-'} prev_hit={prev_hit or '-'} keys={len(merged)}"
            )
    return out


if __name__ == "__main__":
    indicators = load_all_indicators("BTCUSDT", "binance")
    print(json.dumps(indicators, ensure_ascii=False))
