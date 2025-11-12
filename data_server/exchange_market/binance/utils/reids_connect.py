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

    def set_hash(self, key: str, mapping_dict: dict, check_type: bool = True):
        """存储哈希类型。默认检查现有键类型，非 hash 则删除避免 WRONGTYPE。
        Args:
            key: Redis 键名
            mapping_dict: 要写入的字段字典
            check_type: 是否检查并处理现有键类型
        """
        try:
            if check_type:
                ktype = self.conn.type(key)
                if ktype and ktype != "hash":
                    if ktype != "none":
                        self.conn.delete(key)
            self.conn.hset(key, mapping=mapping_dict)
        except Exception as e:
            try:
                ktype = self.conn.type(key)
            except Exception:
                ktype = "unknown"
            print(f"Redis HSET error on key={key} type={ktype}: {e}")

    def get_hash(self, key: str):
        """读取整个哈希。若键不是 hash 或不存在，则返回 None。"""
        try:
            ktype = self.conn.type(key)
            if ktype != "hash":
                return None
            return self.conn.hgetall(key)
        except Exception as e:
            print(f"Redis HGETALL error on key={key}: {e}")
            return None


if __name__ == "__main__":
    rc = RedisClient()
    # 使用集合类型：先删除旧键，避免类型不匹配
    # rc.conn.delete("symbol:binance")
    rc.conn.sadd("symbol:binance", "BTCUSDT")
    print(rc.conn.smembers("symbol:binance"))
