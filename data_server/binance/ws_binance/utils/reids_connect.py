import json
from data_server.binance.ws_binance.utils.redis_client import get_sync_redis


class RedisClient:
    def __init__(self,
                 host=None,
                 port=None,
                 password=None,
                 db=None,):

        self.conn = get_sync_redis(host=host, port=port, password=password, db=db)

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

    def xadd_stream(
        self,
        key: str,
        fields: dict,
        maxlen: int = 50000,
        approximate: bool = True,
        check_type: bool = True,
    ):
        """写入 Redis Stream。默认限制长度，避免无限增长。

        Args:
            key: Stream key
            fields: 字段字典（值会被 Redis 转为字符串）
            maxlen: 最大长度（近似裁剪）
            approximate: 是否使用近似裁剪（性能更好）
            check_type: 是否检查并处理现有键类型
        """
        try:
            if check_type:
                ktype = self.conn.type(key)
                if ktype and ktype != "stream":
                    if ktype != "none":
                        self.conn.delete(key)
            self.conn.xadd(key, fields, maxlen=maxlen, approximate=approximate)
        except Exception as e:
            try:
                ktype = self.conn.type(key)
            except Exception:
                ktype = "unknown"
            print(f"Redis XADD error on key={key} type={ktype}: {e}")

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

    def delete_by_prefix(self, prefix: str) -> int:
        total = 0
        pipe = self.conn.pipeline()
        count = 0
        for key in self.conn.scan_iter(match=f"{prefix}*"):
            pipe.delete(key)
            count += 1
            if count >= 1000:
                res = pipe.execute()
                total += sum(res) if isinstance(res, list) else int(res or 0)
                pipe = self.conn.pipeline()
                count = 0
        if count:
            res = pipe.execute()
            total += sum(res) if isinstance(res, list) else int(res or 0)
        return total


if __name__ == "__main__":
    rc = RedisClient()
    # 使用集合类型：先删除旧键，避免类型不匹配
    # deleted = rc.delete_by_prefix("final")
    # deleted = rc.delete_by_prefix("klines:binance:1000PEPEUSDT")
    # deleted = rc.delete_by_prefix("indicators:binance:1000PEPEUSDT")
    # deleted = rc.delete_by_prefix("market_raw:binance:1000PEPEUSDT")
    # print(f"deleted={deleted}")

    # rc.conn.delete("symbol:BTCUSDT")
    rc.conn.sadd("symbol:binance", "ETHUSDT")
    # print(rc.conn.smembers("symbol:binance"))
