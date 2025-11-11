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
            db=db or int(os.environ.get("REDIS_DB", 0)),
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
    def update_depth(self, symbol: str, depth_data: dict):
        """
        depth_data:
        {
            "bids": [["price1","qty1"], ...],
            "asks": [["price1","qty1"], ...]
        }
        """
        key = f"depth:{symbol}"
        self.set_json(key, depth_data)

    def get_depth(self, symbol: str):
        key = f"depth:{symbol}"
        return self.get_json(key)


if __name__ == "__main__":
    rc = RedisClient()
    # 使用集合类型：先删除旧键，避免类型不匹配
    # rc.conn.delete("symbol:binance")
    rc.conn.sadd("symbol:binance", "btcusdt")
    print(rc.conn.smembers("symbol:binance"))