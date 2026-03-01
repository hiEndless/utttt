"""
暴涨暴跌 & 单边行情触发器

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

事件与字段名对照（中文说明）
- pct_change_up / pct_change_down：短窗口价格涨跌幅超过阈值
  * pct：相对涨跌幅（末价相对首价）
  * p0：窗口首价
  * pN：窗口末价
- zscore_spike：基于收益的 z 分数异常，识别突发波动
  * z：最后一次收益的 z 分数
  * last_ret：最后一次收益（Δp / 前一价）
- bid_collapse：买盘深度相对历史均值显著下降（连续满足）
  * ratio：当前买盘深度 / 历史均值
  * bid_now：当前买盘汇总深度
  * bid_mean：历史窗口买盘平均深度
  * streak：连续满足崩塌条件的次数
- ask_collapse：卖盘深度相对历史均值显著下降（连续满足）
  * ratio：当前卖盘深度 / 历史均值
  * ask_now：当前卖盘汇总深度
  * ask_mean：历史窗口卖盘平均深度
  * streak：连续满足崩塌条件的次数
- one_side_up / one_side_down：单边行情（连续上涨/下跌且总幅度达标）
  * count：连续同方向次数
  * len：窗口内价格点数量
  * pct：窗口总涨跌幅（末价相对首价）
- liquidity_collapse（聚合崩塌事件）：在一个评估周期内合并多个崩塌信号
  * types：包含的事件类型列表
  * count：被合并的事件总数
  * ratio[]：每次事件的当前/均值比
  * bid_now[] / ask_now[]：每次事件的当前深度
  * bid_mean[] / ask_mean[]：每次事件的历史平均深度
  * streak[]：每次事件的连续计数

"""

import asyncio
import time
from collections import deque
import math
import json
import os
from data_server.binance.ws_binance.utils.redis_client import (
    build_url,
    get_async_redis,
    key_alerts,
)

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
        stream_key_template="ticks:binance:{symbol}",
        latest_key_template="price:binance:{symbol}",
        max_stream_len=10000,
        window_seconds=1.0,
        ticks_per_second_estimate=10,
        pct_change_th=0.01,
        zscore_th=5.0,
        depth_ratio_th=0.2,
        debounce_ms=1000,
        cooldown_s=10,
        use_zscore=True,
        confirm_ticks=4,
        min_depth_liq=5.0,
        aggregate_window_ms=2000,
    ):
        """
        参数说明：
        - window_seconds: 价格 & 深度滑动窗口的时间长度，例如 1s/3s/5s
        - ticks_per_second_estimate: 用于估算 deque 缓存长度
        - pct_change_th: % 变化触发阈值（例如 0.005 表示 0.5%）
        - zscore_th: z-score 阈值（仅在 numpy 可用时生效），用于捕捉非常规波动
        - depth_ratio_th: 深度崩塌阈值（当前深度 / 过去平均深度 <= 阈值）
        - confirm_ticks: 需要连续多少 tick 才确认事件
        - debounce_ms: 去抖时间（同一方向重复触发需间隔）
        - cooldown_s: 触发后冷却时间，避免重复告警
        - aggregate_window_ms: 在窗口内把多个相似事件合并
        """
        if redis is None:
            raise RuntimeError("redis.asyncio 未安装，请安装 redis>=4.2 或者改成 aioredis")

        # 从环境变量读取 Redis 连接参数，如果未显式传入 redis_url 则组装
        self.redis_url = redis_url or build_url()
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
        self.use_zscore = use_zscore
        self.confirm_ticks = max(2, int(confirm_ticks))
        self.min_depth_liq = float(min_depth_liq)
        self.aggregate_window_ms = int(aggregate_window_ms)

        # debounce/cooldown
        self.debounce_ms = debounce_ms
        self.cooldown_s = cooldown_s
        self.last_alert_time = {}  # symbol -> timestamp
        self.last_alert_type = {}
        self.streaks = {}  # symbol -> {ask_c:int, bid_c:int, up:int, down:int}
        self.stats = {"counts": {}, "last": {}}

        # callbacks
        self.alert_callback = None

        # redis client
        self.redis = get_async_redis(self.redis_url)

        # 中文注释：写入限频 + 并发保护，避免高频 create_task 抢占连接池导致 "Too many connections"
        self._ticks_write_interval_ms = int(os.getenv("SPIKE_TICKS_WRITE_INTERVAL_MS", "1000") or "1000")
        self._latest_write_interval_ms = int(os.getenv("SPIKE_LATEST_WRITE_INTERVAL_MS", "1000") or "1000")
        self._redis_write_concurrency = int(os.getenv("SPIKE_REDIS_WRITE_CONCURRENCY", "20") or "20")
        self._redis_write_sem = asyncio.Semaphore(max(1, self._redis_write_concurrency))
        self._last_stream_write_ms: dict[str, int] = {}
        self._last_latest_write_ms: dict[str, int] = {}

        # control
        self._running = False

    async def start(self):
        # 预热连接
        await self.redis.ping()
        self._running = True

    async def stop(self):
        self._running = False
        try:
            # redis.asyncio 在不同版本里关闭接口不一致，优先使用 aclose() 回收连接池
            if hasattr(self.redis, "aclose"):
                await self.redis.aclose()
            else:
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
        if symbol not in self.streaks:
            self.streaks[symbol] = {"ask_c": 0, "bid_c": 0, "up": 0, "down": 0}

    def _to_ms(self, ts):
        try:
            v = float(ts)
            # 秒级 -> 毫秒；已是毫秒则直接返回
            return int(v*1000) if v < 1e12 else int(v)
        except Exception:
            return int(time.time()*1000)

    async def add_tick_and_persist(self, symbol, price, bid_liq, ask_liq, ts=None):
        """
        在收到每个 tick 时调用：
        - 将 tick 写入 Redis Stream（用于后续追溯/agent 消费）
        - 更新内存滑动窗口并执行检测
        """
        # 统一：流里写毫秒整数；缓冲区用秒浮点
        if ts is None:
            now_s = time.time()
            ts_ms = int(now_s*1000)
            ts_s = now_s
        else:
            ts_ms = self._to_ms(ts)
            ts_s = ts_ms / 1000.0
        self._ensure_symbol(symbol)

        buf = self.buffers[symbol]
        buf["prices"].append(float(price))
        buf["bids"].append(float(bid_liq))
        buf["asks"].append(float(ask_liq))
        buf["times"].append(float(ts_s))

        # persist to redis stream（XADD）
        stream_key = self.stream_key_template.format(symbol=symbol)
        latest_key = self.latest_key_template.format(symbol=symbol)
        last_stream_ms = self._last_stream_write_ms.get(symbol, 0)
        last_latest_ms = self._last_latest_write_ms.get(symbol, 0)
        should_xadd = (ts_ms - last_stream_ms) >= self._ticks_write_interval_ms
        should_hset = (ts_ms - last_latest_ms) >= self._latest_write_interval_ms

        if should_xadd or should_hset:
            acquired = False
            try:
                await asyncio.wait_for(self._redis_write_sem.acquire(), timeout=0)
                acquired = True
            except Exception:
                acquired = False

            if acquired:
                try:
                    if should_xadd:
                        try:
                            await self.redis.xadd(
                                stream_key,
                                {
                                    "ts": ts_ms,
                                    "price": float(price),
                                    "bid": float(bid_liq),
                                    "ask": float(ask_liq),
                                },
                                maxlen=self.max_stream_len,
                                approximate=True,
                            )
                            self._last_stream_write_ms[symbol] = ts_ms
                        except Exception as e:
                            try:
                                ktype = await self.redis.type(stream_key)
                            except Exception:
                                ktype = "unknown"
                            print(f"redis write error on XADD key={stream_key} type={ktype}: {e}")

                    if should_hset:
                        try:
                            await self.redis.hset(latest_key, mapping={"ts": ts_ms, "price": price, "bid": bid_liq, "ask": ask_liq})
                            self._last_latest_write_ms[symbol] = ts_ms
                        except Exception as e:
                            try:
                                ktype = await self.redis.type(latest_key)
                            except Exception:
                                ktype = "unknown"
                            print(f"redis write error on HSET key={latest_key} type={ktype}: {e}")
                finally:
                    try:
                        self._redis_write_sem.release()
                    except Exception:
                        pass

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
            # 绝对深度门槛：低于门槛时不触发，以免流动性稀薄导致误报
            if bid_mean >= self.min_depth_liq:
                if bid_mean > 0 and bid_now / bid_mean <= self.depth_ratio_th:
                    self.streaks[symbol]["bid_c"] = self.streaks[symbol]["bid_c"] + 1
                else:
                    self.streaks[symbol]["bid_c"] = 0
            else:
                self.streaks[symbol]["bid_c"] = 0

            if ask_mean >= self.min_depth_liq:
                if ask_mean > 0 and ask_now / ask_mean <= self.depth_ratio_th:
                    self.streaks[symbol]["ask_c"] = self.streaks[symbol]["ask_c"] + 1
                else:
                    self.streaks[symbol]["ask_c"] = 0
            else:
                self.streaks[symbol]["ask_c"] = 0

            if self.streaks[symbol]["bid_c"] >= self.confirm_ticks:
                alerts.append(("bid_collapse", {"ratio": float(bid_now/bid_mean), "bid_now": bid_now, "bid_mean": bid_mean, "streak": self.streaks[symbol]["bid_c"]}))
            if self.streaks[symbol]["ask_c"] >= self.confirm_ticks:
                alerts.append(("ask_collapse", {"ratio": float(ask_now/ask_mean), "ask_now": ask_now, "ask_mean": ask_mean, "streak": self.streaks[symbol]["ask_c"]}))

        # 4) 单边行情检测（连续上涨/下跌）
        if len(prices) >= 3:
            last_ret = prices[-1] - prices[-2]
            if last_ret > 0:
                self.streaks[symbol]["up"] += 1
                self.streaks[symbol]["down"] = 0
            elif last_ret < 0:
                self.streaks[symbol]["down"] += 1
                self.streaks[symbol]["up"] = 0
            # 单边需满足：连续 confirm_ticks 次同方向，且总涨跌幅达到阈值
            total_pct = abs(pct_change)
            if self.streaks[symbol]["up"] >= self.confirm_ticks and total_pct >= self.pct_change_th:
                alerts.append(("one_side_up", {"count": int(self.streaks[symbol]["up"]), "len": len(prices), "pct": float(pct_change)}))
            if self.streaks[symbol]["down"] >= self.confirm_ticks and total_pct >= self.pct_change_th:
                alerts.append(("one_side_down", {"count": int(self.streaks[symbol]["down"]), "len": len(prices), "pct": float(pct_change)}))

        # 事件聚合：短时间内的多个相关事件合并
        aggregated = []
        collapse_events = [a for a in alerts if a[0] in ("ask_collapse", "bid_collapse")]
        other_events = [a for a in alerts if a[0] not in ("ask_collapse", "bid_collapse")]
        if collapse_events:
            agg_details = {"types": [t for (t, _) in collapse_events], "count": len(collapse_events)}
            for _, d in collapse_events:
                for k, v in d.items():
                    agg_details.setdefault(k, []).append(v)
            aggregated.append(("liquidity_collapse", agg_details))
        aggregated.extend(other_events)

        # 合并与去抖：检查冷却时间与去抖
        for atype, details in aggregated:
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
        alert_stream = key_alerts(symbol)
        # 统一为毫秒整数时间戳
        payload = {"ts": int(time.time()*1000), "type": alert_type, "details": json.dumps(details)}
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
#    - 是的。推荐：在 detector 触发特殊行情时，写入一个 alerts:binance:{symbol} stream 以及在 redis 做一个短期标记键（EX 5s~60s），
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
