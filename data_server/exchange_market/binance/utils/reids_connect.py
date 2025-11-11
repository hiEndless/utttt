import redis
import json
import os


class RedisClient:
    def __init__(self,
                 host=None,
                 port=None,
                 password=None,
                 db=None,):

        self.conn = redis.Redis(
            host=host or os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=port or int(os.environ.get("REDIS_PORT", 6379)),
            password=password or os.environ.get("REDIS_PASSWORD", None),
            db=db or int(os.environ.get("REDIS_DB", 1)),
            decode_responses=True,
        )

    # ========== 通用 set/get ==========
    def set_json(self, key: str, value):
        """自动 JSON 序列化存储"""
        self.conn.set(key, json.dumps(value))

    def get_json(self, key: str):
        """自动 JSON 反序列化读取"""
        data = self.conn.get(key)
        if not data:
            return None
        return json.loads(data)

    def set_raw(self, key: str, value: str):
        """普通字符串 set"""
        self.conn.set(key, value)

    def get_raw(self, key: str):
        return self.conn.get(key)

    # ========== depth 专用 API ==========
    def update_depth(self, symbol: str, depth_data: dict, ts: int = None):
        """
        depth_data:
        {
            "bids": [["price1","qty1"], ...],
            "asks": [["price1","qty1"], ...]
        }
        """
        key = f"depth:{symbol}"
        self.set_json(key, depth_data)

        # 同步计算 Top10 聚合指标
        self._update_top_depth(symbol, depth_data, ts)

    def _update_top_depth(self, symbol: str, depth_data: dict, ts: int = None, top_n: int = 10):
        """
        聚合深度信息，存到 ticks:{symbol} 最新值
        """
        bids = depth_data.get("bids", [])[:top_n]
        asks = depth_data.get("asks", [])[:top_n]

        if not bids or not asks:
            return

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        bid_qty_sum = sum(float(b[1]) for b in bids)
        ask_qty_sum = sum(float(a[1]) for a in asks)

        # 可选加权平均价
        bid_depth_weighted = sum(float(b[0]) * float(b[1]) for b in bids) / max(bid_qty_sum, 1e-9)
        ask_depth_weighted = sum(float(a[0]) * float(a[1]) for a in asks) / max(ask_qty_sum, 1e-9)

        top_depth_summary = {
            "ts": ts,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "bid_qty": bid_qty_sum,
            "ask_qty": ask_qty_sum,
            "bid_weighted": bid_depth_weighted,
            "ask_weighted": ask_depth_weighted,
        }

        # # 存到 ticks:{symbol} 最新值（方便 SpikeDetector 快速读取）
        # ticks_key = f"ticks:{symbol}"
        # self.set_json(ticks_key, top_depth_summary)

        # 存到 Redis Stream，保留历史
        stream_key = f"ticks:{symbol}"
        try:
            self.conn.xadd(stream_key, {k: v for k, v in top_depth_summary.items()}, maxlen=1000, approximate=True)
        except Exception as e:
            print("Redis XADD error:", e)

    def get_depth(self, symbol: str):
        key = f"depth:{symbol}"
        return self.get_json(key)


if __name__ == "__main__":
    rc = RedisClient()
    # 使用集合类型：先删除旧键，避免类型不匹配
    # rc.conn.delete("symbol:binance")
    rc.conn.sadd("symbol:binance", "btcusdt")
    print(rc.conn.smembers("symbol:binance"))