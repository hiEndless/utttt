# spike_trigger.py

"""
项目集成版 - 暴涨暴跌 & 单边行情触发器

说明：
- 使用 Redis Streams 存储高频价格（XADD，保留固定长度）。
- 同步/异步均支持（示例以 asyncio + aioredis 为主架构）。
- 使用自适应阈值（基于滑动窗口的百分比 + z-score）与去抖（debounce）与冷却（cooldown）。
- 支持深度（bid/ask liquidity）信号的持久化与突发检测。
- 提供简单的回调接口，当触发器检测到警报时会调用用户注册的回调。

集成要点：
1. 把本文件放入项目，按需要调整 Redis 连接和参数。
2. 在订阅到每个 tick（price + depth）时，调用 detector.add_tick_and_persist(...)
3. detector 会在内部异步判断并通过回调发送警报（可接入消息队列/邮件/告警系统）。

依赖：
- aioredis（或 redis.asyncio）
- numpy

示例：
    from spike_trigger import SpikeDetector
    detector = SpikeDetector(...)
    await detector.start()
    # 在 ws 接收循环中：
    await detector.add_tick_and_persist(symbol, price, bid_liq, ask_liq, ts)

"""

import asyncio
import time
from collections import deque
import math
import json
import os

try:
    import numpy as np
except Exception:
    np = None

# 使用 redis.asyncio（redis-py 4.x）或 aioredis
try:
    import redis.asyncio as redis
except Exception:
    redis = None


class SpikeDetector:
    def __init__(
        self,
        redis_url=None,
        stream_key_template="ticks:{symbol}",
        latest_key_template="price:{symbol}",
        max_stream_len=10000,
        window_seconds=1.0,
        ticks_per_second_estimate=10,
        pct_change_th=0.005,
        zscore_th=4.0,
        depth_ratio_th=0.3,
        debounce_ms=200,
        cooldown_s=2,
        use_zscore=True,
    ):
        """
        参数说明：
        - window_seconds: 用于统计的时间窗口（秒），例如 1s/3s/5s
        - ticks_per_second_estimate: 估算每秒 tick 数，用来设定滑动缓存长度
        - pct_change_th: 简单百分比阈值（例如 0.005 表示 0.5%）
        - zscore_th: z-score 阈值（仅在 numpy 可用时生效），用于捕捉非常规波动
        - depth_ratio_th: 深度突降阈值（当前深度 / 过去平均深度 <= 阈值）
        - debounce_ms: 去抖时间（同一方向重复触发需间隔）
        - cooldown_s: 触发后冷却时间，避免重复告警
        """
        if redis is None:
            raise RuntimeError("redis.asyncio 未安装，请安装 redis>=4.2 或者改成 aioredis")

        # 从环境变量读取 Redis 连接参数，如果未显式传入 redis_url 则组装
        if not redis_url:
            host = os.environ.get("REDIS_HOST", "127.0.0.1")
            port = os.environ.get("REDIS_PORT", "6379")
            db = os.environ.get("REDIS_DB", "1")
            password = os.environ.get("REDIS_PASSWORD", None)
            if password:
                self.redis_url = f"redis://:{password}@{host}:{port}/{db}"
            else:
                self.redis_url = f"redis://{host}:{port}/{db}"
        else:
            self.redis_url = redis_url
        self.stream_key_template = stream_key_template
        self.latest_key_template = latest_key_template
        self.max_stream_len = max_stream_len
        self.window_seconds = window_seconds
        self.ticks_cache_len = max(3, int(window_seconds * ticks_per_second_estimate))

        # sliding in-memory buffers（每个symbol独立）
        self.buffers = {}  # symbol -> {prices: deque, bids: deque, asks: deque, times: deque}

        # thresholds
        self.pct_change_th = pct_change_th
        self.zscore_th = zscore_th
        self.depth_ratio_th = depth_ratio_th

        # debounce/cooldown
        self.debounce_ms = debounce_ms
        self.cooldown_s = cooldown_s
        self.last_alert_time = {}  # symbol -> timestamp
        self.last_alert_type = {}

        # callbacks
        self.alert_callback = None

        # redis client
        self.redis = redis.from_url(self.redis_url, decode_responses=True)

        # control
        self._running = False

    async def start(self):
        # 预热连接
        await self.redis.ping()
        self._running = True

    async def stop(self):
        self._running = False
        try:
            await self.redis.close()
        except Exception:
            pass

    def register_alert_callback(self, cb):
        """cb(symbol, alert_type, details:dict) -> None"""
        self.alert_callback = cb

    def _ensure_symbol(self, symbol):
        if symbol not in self.buffers:
            self.buffers[symbol] = {
                "prices": deque(maxlen=self.ticks_cache_len),
                "bids": deque(maxlen=self.ticks_cache_len),
                "asks": deque(maxlen=self.ticks_cache_len),
                "times": deque(maxlen=self.ticks_cache_len),
            }

    async def add_tick_and_persist(self, symbol, price, bid_liq, ask_liq, ts=None):
        """
        在收到每个 tick 时调用：
        - 将 tick 写入 Redis Stream（用于后续追溯/agent 消费）
        - 更新内存滑动窗口并执行检测
        """
        if ts is None:
            ts = time.time()
        self._ensure_symbol(symbol)

        buf = self.buffers[symbol]
        buf["prices"].append(float(price))
        buf["bids"].append(float(bid_liq))
        buf["asks"].append(float(ask_liq))
        buf["times"].append(float(ts))

        # persist to redis stream（XADD）
        stream_key = self.stream_key_template.format(symbol=symbol)
        latest_key = self.latest_key_template.format(symbol=symbol)
        try:
            # XADD: 支持 capped stream
            await self.redis.xadd(stream_key, {
                "ts": ts,
                "price": float(price),
                "bid": float(bid_liq),
                "ask": float(ask_liq)
            }, maxlen=self.max_stream_len, approximate=True)
            # 也保持一个最新值，便于快速查询
            await self.redis.hset(latest_key, mapping={"ts": ts, "price": price, "bid": bid_liq, "ask": ask_liq})
        except Exception as e:
            # 不要因为 redis 写失败阻塞检测，记录日志即可
            print("redis write error:", e)

        # 非阻塞触发检测
        asyncio.create_task(self._evaluate(symbol))

    async def _evaluate(self, symbol):
        """执行检测逻辑，若满足条件则触发回调"""
        buf = self.buffers[symbol]
        prices = list(buf["prices"])
        bids = list(buf["bids"]) if len(buf["bids"])>0 else None
        asks = list(buf["asks"]) if len(buf["asks"])>0 else None
        times = list(buf["times"]) if len(buf["times"])>0 else None

        now = time.time()
        # 基本要求：至少 2 个点
        if len(prices) < 2:
            return

        # 1) 简单百分比变化
        p0 = prices[0]
        pN = prices[-1]
        pct_change = (pN - p0) / (p0 + 1e-12)

        alerts = []

        if abs(pct_change) >= self.pct_change_th:
            direction = "up" if pct_change > 0 else "down"
            alerts.append((f"pct_change_{direction}", {"pct": pct_change, "p0": p0, "pN": pN}))

        # 2) z-score 异常（如果 numpy 可用）
        if self.use_zscore and np is not None and len(prices) >= 4:
            arr = np.array(prices)
            # 用增量（returns）计算 zscore 能更敏感地发现突发波动
            returns = np.diff(arr) / (arr[:-1] + 1e-12)
            mu = returns.mean()
            sigma = returns.std(ddof=0)
            if sigma > 0:
                z = (returns[-1] - mu) / sigma
                if abs(z) >= self.zscore_th:
                    alerts.append(("zscore_spike", {"z": float(z), "last_ret": float(returns[-1])}))

        # 3) 深度崩塌（当前深度 / 窗口平均深度 <= depth_ratio_th）
        if bids is not None and asks is not None and len(bids) >= 3:
            bid_now = bids[-1]
            ask_now = asks[-1]
            bid_mean = sum(bids[:-1]) / max(1, len(bids[:-1]))
            ask_mean = sum(asks[:-1]) / max(1, len(asks[:-1]))
            if bid_mean > 0 and bid_now / bid_mean <= self.depth_ratio_th:
                alerts.append(("bid_collapse", {"ratio": float(bid_now/bid_mean), "bid_now": bid_now, "bid_mean": bid_mean}))
            if ask_mean > 0 and ask_now / ask_mean <= self.depth_ratio_th:
                alerts.append(("ask_collapse", {"ratio": float(ask_now/ask_mean), "ask_now": ask_now, "ask_mean": ask_mean}))

        # 4) 单边行情检测（连续上涨/下跌）
        if len(prices) >= 3:
            ups = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])
            downs = sum(1 for i in range(1, len(prices)) if prices[i] < prices[i-1])
            if ups == len(prices)-1:
                alerts.append(("one_side_up", {"count": ups, "len": len(prices)}))
            if downs == len(prices)-1:
                alerts.append(("one_side_down", {"count": downs, "len": len(prices)}))

        # 合并与去抖：检查冷却时间与去抖
        for atype, details in alerts:
            last_t = self.last_alert_time.get(symbol, 0)
            last_type = self.last_alert_type.get(symbol)
            # 冷却
            if now - last_t < self.cooldown_s:
                continue
            # 简单去抖：同类型在 debounce_ms 内忽略
            if last_type == atype and (now - last_t) * 1000 < self.debounce_ms:
                continue
            # 触发
            self.last_alert_time[symbol] = now
            self.last_alert_type[symbol] = atype
            await self._notify_alert(symbol, atype, details)

    async def _notify_alert(self, symbol, alert_type, details):
        # 将警报写入 redis 专门的 stream 或者调用回调
        alert_stream = f"alerts:{symbol}"
        payload = {"ts": time.time(), "type": alert_type, "details": json.dumps(details)}
        try:
            await self.redis.xadd(alert_stream, payload, maxlen=1000, approximate=True)
        except Exception as e:
            print("alert redis write error:", e)

        if self.alert_callback:
            # callback 可以同步或异步，支持两者
            if asyncio.iscoroutinefunction(self.alert_callback):
                try:
                    await self.alert_callback(symbol, alert_type, details)
                except Exception as e:
                    print("alert callback error", e)
            else:
                try:
                    self.alert_callback(symbol, alert_type, details)
                except Exception as e:
                    print("alert callback error", e)


# ---------- 示例集成（ws loop 中如何使用） ----------
# (1) 初始化
# detector = SpikeDetector(redis_url="redis://127.0.0.1:6379/0")
# await detector.start()
# detector.register_alert_callback(my_alert_handler)

# (2) 在 websocket 的接收循环里：
# async for message in ws:
#     data = parse(message)
#     # 假设解析出 symbol, price, bid_liq, ask_liq
#     await detector.add_tick_and_persist(symbol, price, bid_liq, ask_liq)

# (3) my_alert_handler 示例：
# async def my_alert_handler(symbol, alert_type, details):
#     print("ALERT", symbol, alert_type, details)
#     # 进一步处理：发邮件、发 slack、写数据库、触发 agent 等


# ---------- 说明与建议 ----------
# 1) tick 存储策略：
#    - 使用 Redis Stream（XADD）是高并发场景的常见做法，支持消费组、回溯。
#    - 同时保留一个 latest hash key 方便快速读到当前价（HSET）。
#    - 如果需要时间序列聚合，也可以在后台周期性任务中把 stream 聚合写入 TSDB 或数据库。
#
# 2) 是否存 list 还是只存当前值：
#    - 推荐：两者都做：一是把高速流写入 stream（用于回溯/agent），二是写 latest key（用于低延迟快速查询）。
#    - 只存 current 会丢失历史；只存 list（未压缩）会导致内存压力大。
#
# 3) 100ms 的速度是否过快：
#    - Redis Stream 支持很高吞吐；关键是消费端能否跟上。agent 通常不需要每个 100ms tick 单独处理。
#    - 建议：
#        * 把原始 tick 写入 stream（完整保存短期历史），
#        * agent 从 stream 或从聚合表消费，但可按需做 downsample（例如 200ms/500ms/1s 聚合），
#        * 检测器可以在内存中以更高频率运行（100ms）以捕获瞬时波动，但告警下游可合并/去噪。
#
# 4) 是否实时计算趋势并标记特殊键：
#    - 是的。推荐：在 detector 触发特殊行情时，写入一个 alerts:{symbol} stream 以及在 redis 做一个短期标记键（EX 5s~60s），
#      例如 SET special:{symbol}:{type} = 1 EX 10。
#    - 这样其他 agent 可以快速查询是否处于特殊行情并调整行为（比如暂停下单或降低仓位）。
#
# 5) 是否获取市场深度信号：
#    - 强烈建议获取深度信息（至少 top-5 或 top-10 汇总的 bid/ask liquidity），
#    - 深度崩塌（liquidity collapse）比单纯价格波动更能说明市场流动性问题，适用于判断“洗盘/闪崩/单边行情”。
#
# 6) 关于窗口长度（1s 是否过苛刻）：
#    - 1s 窗口对于高频场景是合理的，但确实存在“瞬间回弹”导致的误报。
#    - 改进建议：
#        * 使用多层窗口：短窗口（200–1000ms）用来快速侦测，长窗口（3s/10s）用来确认；
#        * 触发条件分级：短窗口触发后进入观察期（observe），只有若长窗口仍异常才升级为严重警报；
#        * 引入冷却 + 自动抑制（同一方向的重复触发在短时间内降级）。
#
# 7) 误报处理示例：
#    - 在短窗口触发后，把一个临时键写入 redis（special:pending:{symbol}），设置较短 TTL（例如 1-3s），
#    - 如果在 pending 期间长窗口确认仍异常，则写入 final alert 并通知 agent；否则删除 pending 并不通知。
#
# 8) 性能注意：
#    - 如果你订阅上千个币对，避免为每个 symbol 都创建大量 asyncio 任务。可以用批处理（把多个 tick 按时间窗聚合后处理）。
#    - Redis 写入应做容错与限速：在极端情况下可以只写 latest 并降采样写 stream（例如 10ms 内只写一次）。

# End of file
