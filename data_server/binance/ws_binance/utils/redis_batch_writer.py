"""
Redis批量写入队列（解决Too many connections问题）
使用异步队列缓冲高频写入操作，批量执行，减少连接使用
"""

import asyncio
import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional
from data_server.binance.ws_binance.utils.redis_client import get_sync_redis, get_async_redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # 减少日志噪音


class RedisBatchWriter:
    """
    Redis批量写入队列（解决Too many connections问题）
    
    功能：
    - 缓冲高频写入操作
    - 批量执行，减少连接使用
    - 自动刷新（定时批量写入）
    - 支持XADD和HSET操作
    """
    
    def __init__(
        self,
        batch_size: int = 50,  # 批量大小
        flush_interval: float = 0.5,  # 刷新间隔（秒）
        use_async: bool = False  # 是否使用异步Redis
    ):
        """
        初始化批量写入队列
        
        Args:
            batch_size: 批量大小，达到此数量时自动刷新
            flush_interval: 刷新间隔（秒），定时刷新
            use_async: 是否使用异步Redis
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.use_async = use_async
        
        # 批量队列
        self.xadd_queue: List[Tuple[str, Dict[str, Any], Optional[int], Optional[bool]]] = []  # (key, fields, maxlen, approximate)
        self.hset_queue: List[Tuple[str, Dict[str, Any]]] = []  # (key, mapping)
        
        # 锁
        self._lock = asyncio.Lock() if use_async else None
        
        # Redis客户端
        if use_async:
            self.redis = get_async_redis(max_connections=50)  # 批量写入使用较小的连接池
        else:
            self.redis = get_sync_redis(max_connections=50)
        
        # 运行状态
        self._running = False
        self._task = None
    
    def add_xadd(self, key: str, fields: Dict[str, Any], maxlen: Optional[int] = None, approximate: bool = True):
        """
        添加XADD操作到队列（线程安全，支持同步和异步调用）
        
        Args:
            key: Redis Stream键
            fields: 字段字典
            maxlen: 最大长度
            approximate: 是否近似截断
        """
        import threading
        if not hasattr(self, '_thread_lock'):
            self._thread_lock = threading.Lock()
        
        with self._thread_lock:
            self.xadd_queue.append((key, fields, maxlen, approximate))
            if len(self.xadd_queue) >= self.batch_size:
                # 触发刷新（在后台线程中执行）
                if self.use_async:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self._flush_async())
                    except RuntimeError:
                        pass
                else:
                    # 同步版本：在后台线程中刷新
                    threading.Thread(target=self._flush_sync, daemon=True).start()
    
    def add_hset(self, key: str, mapping: Dict[str, Any]):
        """
        添加HSET操作到队列（线程安全，支持同步和异步调用）
        
        Args:
            key: Redis Hash键
            mapping: 字段字典
        """
        import threading
        if not hasattr(self, '_thread_lock'):
            self._thread_lock = threading.Lock()
        
        with self._thread_lock:
            self.hset_queue.append((key, mapping))
            if len(self.hset_queue) >= self.batch_size:
                # 触发刷新
                if self.use_async:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self._flush_async())
                    except RuntimeError:
                        pass
                else:
                    # 同步版本：在后台线程中刷新
                    threading.Thread(target=self._flush_sync, daemon=True).start()
    
    async def _flush_async(self):
        """异步刷新队列"""
        async with self._lock:
            if not self.xadd_queue and not self.hset_queue:
                return
            
            xadd_batch = self.xadd_queue[:self.batch_size]
            hset_batch = self.hset_queue[:self.batch_size]
            
            self.xadd_queue = self.xadd_queue[self.batch_size:]
            self.hset_queue = self.hset_queue[self.batch_size:]
        
        # 批量执行XADD
        for key, fields, maxlen, approximate in xadd_batch:
            try:
                await self.redis.xadd(key, fields, maxlen=maxlen, approximate=approximate)
            except Exception as e:
                logger.debug(f"Redis XADD error on key={key}: {e}")
        
        # 批量执行HSET（使用管道）
        if hset_batch:
            try:
                pipe = self.redis.pipeline()
                for key, mapping in hset_batch:
                    pipe.hset(key, mapping=mapping)
                await pipe.execute()
            except Exception as e:
                logger.debug(f"Redis HSET batch error: {e}")
    
    async def _flush_sync_wrapper(self):
        """同步版本的刷新包装器"""
        # 在后台线程中执行同步操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._flush_sync)
    
    def _flush_sync(self):
        """同步刷新队列（线程安全）"""
        import threading
        if not hasattr(self, '_thread_lock'):
            self._thread_lock = threading.Lock()
        
        with self._thread_lock:
            if not self.xadd_queue and not self.hset_queue:
                return
            
            xadd_batch = self.xadd_queue[:self.batch_size]
            hset_batch = self.hset_queue[:self.batch_size]
            
            self.xadd_queue = self.xadd_queue[self.batch_size:]
            self.hset_queue = self.hset_queue[self.batch_size:]
        
        # 批量执行XADD（快速连续执行，减少连接获取/释放开销）
        # 注意：XADD的maxlen参数在pipeline中可能不支持，所以单独执行
        # 但使用同一个连接，减少连接获取开销
        if xadd_batch:
            try:
                # 快速连续执行，使用同一个连接
                for key, fields, maxlen, approximate in xadd_batch:
                    try:
                        self.redis.xadd(key, fields, maxlen=maxlen, approximate=approximate)
                    except Exception as e:
                        # 只记录错误，不中断批量执行
                        logger.debug(f"Redis XADD error on key={key}: {e}")
            except Exception as e:
                logger.debug(f"Redis XADD batch error: {e}")
        
        # 批量执行HSET（使用管道）
        if hset_batch:
            try:
                pipe = self.redis.pipeline()
                for key, mapping in hset_batch:
                    pipe.hset(key, mapping=mapping)
                pipe.execute()
            except Exception as e:
                logger.debug(f"Redis HSET batch error: {e}")
    
    async def _flush_loop(self):
        """定时刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                if self.use_async:
                    await self._flush_async()
                else:
                    # 同步版本：在后台线程中刷新
                    import threading
                    threading.Thread(target=self._flush_sync, daemon=True).start()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def start(self):
        """启动批量写入服务"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())
        logger.info(f"Redis批量写入服务已启动 (batch_size={self.batch_size}, flush_interval={self.flush_interval}s)")
    
    async def stop(self):
        """停止批量写入服务"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # 刷新剩余队列
        if self.use_async:
            await self._flush_async()
        else:
            # 同步版本：直接调用
            self._flush_sync()
        
        logger.info("Redis批量写入服务已停止")
    
    def flush_now(self):
        """立即刷新队列（同步版本）"""
        if not self.use_async:
            self._flush_sync()


# 全局批量写入器（同步版本，用于高频写入）
_global_batch_writer: Optional[RedisBatchWriter] = None


def get_batch_writer() -> RedisBatchWriter:
    """
    获取全局批量写入器
    
    Returns:
        RedisBatchWriter实例
    """
    global _global_batch_writer
    if _global_batch_writer is None:
        _global_batch_writer = RedisBatchWriter(
            batch_size=50,  # 每50个操作批量写入
            flush_interval=0.5,  # 每0.5秒刷新一次
            use_async=False  # 使用同步版本（因为depth.py是同步的）
        )
    return _global_batch_writer


# 异步批量写入器（用于异步代码）
_async_batch_writer: Optional[RedisBatchWriter] = None


def get_async_batch_writer() -> RedisBatchWriter:
    """
    获取异步批量写入器
    
    Returns:
        RedisBatchWriter实例（异步版本）
    """
    global _async_batch_writer
    if _async_batch_writer is None:
        _async_batch_writer = RedisBatchWriter(
            batch_size=50,
            flush_interval=0.5,
            use_async=True
        )
    return _async_batch_writer
