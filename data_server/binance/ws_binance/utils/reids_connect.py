import json
import os
import threading
import time
from typing import Dict, List, Tuple, Optional
from data_server.binance.ws_binance.utils.redis_client import get_sync_redis


class SyncRedisBatchWriter:
    """
    同步 Redis 批量写入器，支持海量数据瞬时插入
    
    使用 pipeline 批量执行写入操作，减少网络往返次数。
    支持自动刷新和手动刷新。
    """
    
    def __init__(self, conn, batch_size: int = 100, flush_interval: float = 0.1):
        """
        Args:
            conn: Redis 连接对象
            batch_size: 批量写入大小，达到此数量时自动刷新
            flush_interval: 自动刷新间隔（秒），即使未达到 batch_size 也会刷新
        """
        self.conn = conn
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._pipeline: Optional[object] = None
        self._pending_ops: List[Tuple[str, tuple, dict]] = []  # (method, args, kwargs)
        self._last_flush_time = time.time()
        self._lock = threading.Lock()
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_flush_thread = False
    
    def _flush(self):
        """刷新 pipeline，执行所有待处理的操作"""
        if not self._pending_ops:
            return
        
        pipeline = self.conn.pipeline()
        for method_name, args, kwargs in self._pending_ops:
            method = getattr(pipeline, method_name)
            method(*args, **kwargs)
        
        try:
            pipeline.execute()
        except Exception as e:
            # 记录错误但不抛出，避免影响其他操作
            print(f"redis_batch_write_error: {e}")
        finally:
            self._pending_ops.clear()
            self._pipeline = None
            self._last_flush_time = time.time()
    
    def _auto_flush_check(self):
        """检查是否需要自动刷新"""
        current_time = time.time()
        should_flush = (
            len(self._pending_ops) >= self.batch_size or
            (self._pending_ops and current_time - self._last_flush_time >= self.flush_interval)
        )
        if should_flush:
            self._flush()
    
    def hset(self, key: str, mapping: dict = None, **kwargs):
        """批量 HSET 操作
        
        Args:
            key: Redis 键名
            mapping: 字段字典（使用 mapping 参数）
            **kwargs: 其他参数（如 name=value 形式）
        """
        with self._lock:
            # Redis pipeline 的 hset 支持两种格式：
            # 1. hset(key, mapping={...}) - 推荐
            # 2. hset(key, name, value, name2, value2, ...)
            if mapping is not None:
                self._pending_ops.append(("hset", (key,), {"mapping": mapping, **kwargs}))
            else:
                # 如果没有 mapping，使用 kwargs 作为字段
                self._pending_ops.append(("hset", (key,), kwargs))
            self._auto_flush_check()
    
    def xadd(self, key: str, fields: dict, *args, **kwargs):
        """批量 XADD 操作"""
        with self._lock:
            self._pending_ops.append(("xadd", (key, fields) + args, kwargs))
            self._auto_flush_check()
    
    def set(self, key: str, value: str, *args, **kwargs):
        """批量 SET 操作"""
        with self._lock:
            self._pending_ops.append(("set", (key, value) + args, kwargs))
            self._auto_flush_check()
    
    def flush(self):
        """手动刷新，立即执行所有待处理的操作"""
        with self._lock:
            self._flush()
    
    def close(self):
        """关闭批量写入器，刷新所有待处理的操作"""
        with self._lock:
            self._stop_flush_thread = True
            self._flush()


# 全局批量写入器缓存（按连接对象缓存）
_BATCH_WRITERS: Dict[object, SyncRedisBatchWriter] = {}
_BATCH_WRITERS_LOCK = threading.Lock()


def get_batch_writer(conn, batch_size: int = None, flush_interval: float = None) -> SyncRedisBatchWriter:
    """
    获取批量写入器（单例模式）
    
    每个连接对象共享一个批量写入器。
    """
    if batch_size is None:
        batch_size = int(os.environ.get("REDIS_BATCH_SIZE", 100))
    if flush_interval is None:
        flush_interval = float(os.environ.get("REDIS_FLUSH_INTERVAL", 0.1))
    
    with _BATCH_WRITERS_LOCK:
        if conn not in _BATCH_WRITERS:
            _BATCH_WRITERS[conn] = SyncRedisBatchWriter(
                conn=conn,
                batch_size=batch_size,
                flush_interval=flush_interval
            )
        return _BATCH_WRITERS[conn]


class RedisClient:
    def __init__(self,
                 host=None,
                 port=None,
                 password=None,
                 db=None,
                 use_batch: bool = True):
        """
        Args:
            host: Redis 主机
            port: Redis 端口
            password: Redis 密码
            db: Redis 数据库编号
            use_batch: 是否使用批量写入（默认 True，提高性能）
        """
        self.conn = get_sync_redis(host=host, port=port, password=password, db=db)
        self.use_batch = use_batch
        if use_batch:
            self._batch_writer = get_batch_writer(self.conn)
        else:
            self._batch_writer = None

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
            mapping_dict: 要写入的字段字典（值会被自动转换为字符串）
            check_type: 是否检查并处理现有键类型
        """
        try:
            if check_type:
                ktype = self.conn.type(key)
                if ktype and ktype != "hash":
                    if ktype != "none":
                        self.conn.delete(key)
            
            # 确保所有值都是字符串（Redis 要求）
            str_mapping = {k: str(v) for k, v in mapping_dict.items()}
            
            if self.use_batch and self._batch_writer:
                # 使用批量写入
                self._batch_writer.hset(key, mapping=str_mapping)
            else:
                # 直接写入
                self.conn.hset(key, mapping=str_mapping)
        except Exception as e:
            try:
                ktype = self.conn.type(key)
            except Exception:
                ktype = "unknown"
            print(f"redis write error on HSET key={key} type={ktype}: {e}")

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
            fields: 字段字典（值会被自动转换为字符串）
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
            
            # 确保所有值都是字符串（Redis Stream 要求）
            str_fields = {k: str(v) for k, v in fields.items()}
            
            if self.use_batch and self._batch_writer:
                # 使用批量写入
                self._batch_writer.xadd(key, str_fields, maxlen=maxlen, approximate=approximate)
            else:
                # 直接写入
                self.conn.xadd(key, str_fields, maxlen=maxlen, approximate=approximate)
        except Exception as e:
            try:
                ktype = self.conn.type(key)
            except Exception:
                ktype = "unknown"
            print(f"redis write error on XADD key={key} type={ktype}: {e}")

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
