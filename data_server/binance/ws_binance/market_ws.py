import asyncio
import json
import os
import threading
import websockets
import logging
import ssl
import time

import requests

from data_server.binance.ws_binance.utils.force_order import handle_force_order
from data_server.binance.ws_binance.utils.reids_connect import RedisClient
from data_server.binance.ws_binance.utils.spike_trigger import SpikeDetector
from data_server.binance.ws_binance.utils.depth import update_depth

redis_client = RedisClient()

# REST 最新成交写入 price:binance（用 /fapi/v1/trades 第一条，与页面显示一致）
# 直接 conn.hset 写入，不经过 batch writer，避免 Too many connections 等导致写入失败
BINANCE_TRADES_URL_MAIN = "https://fapi.binance.com/fapi/v1/trades"
BINANCE_TRADES_URL_TEST = "https://testnet.binancefuture.com/fapi/v1/trades"


def _write_price_direct(key: str, ts_ms: int, price: float):
    """直接写入 Redis，绕过 batch writer，确保 price:binance 能成功更新。"""
    try:
        ktype = redis_client.conn.type(key)
        if ktype and ktype != "hash" and ktype != "none":
            redis_client.conn.delete(key)
        redis_client.conn.hset(key, mapping={"ts": str(ts_ms), "price": str(price)})
    except Exception as e:
        logging.warning(f"[REST trades] Redis HSET key={key} error: {e}")


def _rest_ticker_write_loop_thread(interval_s: float = 0.8):
    """
    在独立线程中运行，定时从 REST 拉取最新成交写入 Redis。
    不依赖 asyncio 事件循环，避免 WS 消息高峰时被阻塞导致写入间隔拉长。
    """
    use_testnet = os.environ.get("BINANCE_TESTNET", "true").strip().lower() in ("1", "true", "yes", "on")
    base_url = BINANCE_TRADES_URL_TEST if use_testnet else BINANCE_TRADES_URL_MAIN

    def fetch_latest_trade_price(symbol: str):
        try:
            r = requests.get(base_url, params={"symbol": symbol, "limit": 1}, timeout=5)
            if r.status_code != 200:
                return None, None
            data = r.json()
            if not isinstance(data, list) or len(data) == 0:
                return None, None
            first = data[0]
            p = first.get("price") or first.get("p")
            t = first.get("time") or first.get("T")
            if p is not None:
                price = float(p)
                ts_ms = int(t) if t is not None else int(time.time() * 1000)
                return price, ts_ms
        except Exception as e:
            logging.warning(f"[REST trades] {symbol} error: {e}")
        return None, None

    logging.info("[REST trades] price:binance 写入任务已启动（独立线程），间隔 %.1fs", interval_s)
    while True:
        try:
            raw = redis_client.conn.smembers("symbol:binance")
            symbols = {str(s).upper() for s in raw} if raw else set()
            for sym in symbols:
                price, ts_ms = fetch_latest_trade_price(sym)
                if price is not None and price > 0:
                    key = f"price:binance:{sym}"
                    _write_price_direct(key, ts_ms, price)
        except Exception as e:
            logging.warning(f"[REST trades] loop error: {e}")
        time.sleep(interval_s)


# ---- SpikeDetector integration state ----
# 使用更稳健的触发器参数，降低高频误报：
# - 1% 百分比阈值、zscore >= 5
# - 去抖 1000ms，冷却 10s
# - 连续确认 4 tick；深度最低门槛 5.0
# - 聚合窗口 2000ms 合并流动性崩塌事件
detector = SpikeDetector(
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
)
_price_cache = {}
_depth_liq_cache = {}  # symbol -> (bid_liq, ask_liq)


def _sum_liquidity(levels):
    """Sum quantities from depth levels [[price, qty], ...]."""
    try:
        return sum(float(q) for _, q in levels)
    except Exception:
        try:
            return sum(float(l[1]) for l in levels)
        except Exception:
            return 0.0


def _cleanup_symbol_keys(symbol: str, max_retries: int = 3):
    """更健壮的清理：扫描并批量删除与 symbol 关联的所有 Redis 键。
    - 使用 scan_iter 匹配大小写两种 symbol
    - 支持重试与删除统计
    - 终端直接 print 日志，确保可见
    - 同时清理本地缓存，以避免后续残留写入
    """
    # 构建匹配模式（大小写都覆盖）
    syms = {symbol, symbol.lower(), symbol.upper()}
    patterns = []
    for sym in syms:
        patterns.extend([
            f"price:binance:{sym}",
            f"depth:binance:{sym}",
            f"ticks:binance:{sym}",
            f"aggtrades:binance:{sym}",
            f"alerts:binance:{sym}",
            f"force_stream:binance:{sym}",
            f"stats:binance:{sym}",
        ])

    # 扫描待删除键集合
    to_delete = set()
    for pat in patterns:
        try:
            for k in redis_client.conn.scan_iter(pat):
                to_delete.add(k)
        except Exception as e:
            print(f"[CLEANUP] scan pattern={pat} error: {e}")

    # 删除前清理本地缓存
    try:
        _price_cache.pop(symbol, None)
        _depth_liq_cache.pop(symbol, None)
    except Exception:
        pass

    if not to_delete:
        print(f"[CLEANUP] no keys matched for {symbol}")
        return

    # 重试批量删除
    remaining = to_delete
    attempt = 0
    while attempt < max_retries and remaining:
        attempt += 1
        try:
            pipe = redis_client.conn.pipeline(transaction=False)
            for k in list(remaining):
                pipe.delete(k)
            pipe.execute()
        except Exception as e:
            print(f"[CLEANUP] pipeline delete error attempt={attempt}: {e}")

        # 重新扫描剩余
        still = set()
        for pat in patterns:
            try:
                for k in redis_client.conn.scan_iter(pat):
                    still.add(k)
            except Exception as e:
                print(f"[CLEANUP] rescan pattern={pat} error: {e}")
        print(
            f"[CLEANUP] attempt {attempt}: tried {len(remaining)} deletions; remaining {len(still)}"
        )
        remaining = still

    if remaining:
        # 最终仍有残留，打印示例键方便排查
        sample = sorted(list(remaining))[:10]
        print(
            f"[CLEANUP] warning: {len(remaining)} keys still present for {symbol}: {sample}"
        )


class BinanceMarketWS:
    BASE_URL = "wss://fstream.binance.com"

    def __init__(
        self,
        streams,
        on_message,
        ping_interval=180,
        timeout=20,
    ):
        self.streams = set(streams)
        self.on_message = on_message
        self.ping_interval = ping_interval
        self.timeout = timeout
        self.ssl_context = ssl._create_unverified_context()

        self.ws = None
        self._task = None
        self._stop = False

        self._lock = asyncio.Lock()
        self._need_reconnect = False

    # -----------------------------
    # Build URL
    # -----------------------------
    def _build_url(self):
        if not self.streams:
            return None
        if len(self.streams) == 1:
            return f"{self.BASE_URL}/ws/{list(self.streams)[0]}"
        return f"{self.BASE_URL}/stream?streams={'/'.join(self.streams)}"

    # -----------------------------
    # Connect
    # -----------------------------
    async def _connect(self):
        url = self._build_url()
        if url is None:
            # logging.warning("[WS] No streams subscribed.")
            return None

        logging.info(f"[WS] Connecting => {url}")

        return await websockets.connect(
            url,
            ssl=self.ssl_context,
            ping_interval=self.ping_interval,
            ping_timeout=self.timeout,
            max_queue=None,
        )

    async def _safe_close(self):
        try:
            if self.ws and not self.ws.closed:
                await self.ws.close()
        except:
            pass

    # -----------------------------
    # Main recv loop
    # -----------------------------
    async def _recv_loop(self):
        while not self._stop:
            try:
                self.ws = await self._connect()
                if self.ws is None:
                    await asyncio.sleep(0.2)
                    continue

                async for msg in self.ws:
                    if self._need_reconnect:
                        break  # 🚀 立即退出，强制重连

                    try:
                        data = json.loads(msg)
                    except:
                        continue

                    if "stream" in data and "data" in data:
                        await self.on_message(data["data"])
                    else:
                        await self.on_message(data)

            except Exception as e:
                logging.warning(f"[WS] Disconnected: {e}")

            finally:
                await self._safe_close()

                if self._need_reconnect:
                    logging.info("[WS] Applying new subscriptions...")
                    self._need_reconnect = False

                # ⭐ 不给 Binance 时间，就没法重连（必须）
                await asyncio.sleep(0.5)

    # -----------------------------
    # Public methods
    # -----------------------------
    async def start(self):
        if self._task:
            return
        self._stop = False
        self._task = asyncio.create_task(self._recv_loop())

    async def stop(self):
        self._stop = True
        await self._safe_close()
        if self._task:
            await self._task

    # -----------------------------
    # ✅ Dynamic subscribe / unsubscribe
    # -----------------------------
    async def add_stream(self, stream: str):
        async with self._lock:
            if stream in self.streams:
                return
            self.streams.add(stream)
            self._need_reconnect = True
            await self._safe_close()  # 强制断开当前连接

    async def remove_stream(self, stream: str):
        async with self._lock:
            if stream not in self.streams:
                return
            self.streams.remove(stream)
            self._need_reconnect = True
            await self._safe_close()  # 强制断开当前连接


async def monitor_symbols(ws, poll_interval=1.0):
    """监控redis，启动/关闭订阅"""
    key_name = "symbol:binance"
    active_symbols = set()
    while True:
        try:
            key_type = redis_client.conn.type(key_name)

            symbols = set()
            if key_type == "set":
                raw = redis_client.conn.smembers(key_name)
                symbols = {str(x) for x in raw}

            # 新增订阅
            for sym in symbols - active_symbols:
                print("新增订阅:", symbols)
                await ws.add_stream(f"{sym.lower()}@aggTrade")
                await ws.add_stream(f"{sym.lower()}@depth20@500ms")
                await ws.add_stream(f"{sym.lower()}@forceOrder")
                active_symbols.add(sym)

            # 移除订阅
            for sym in active_symbols - symbols:
                print("移除订阅:", symbols)
                await ws.remove_stream(f"{sym.lower()}@aggTrade")
                await ws.remove_stream(f"{sym.lower()}@depth20@500ms")
                await ws.remove_stream(f"{sym.lower()}@forceOrder")
                # 清理对应的 Redis 键
                _cleanup_symbol_keys(sym.upper())
                active_symbols.remove(sym)

            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"[SYMBOL WATCH] error: {e}")
            await asyncio.sleep(poll_interval)


async def on_msg(msg):
    """数据处理"""
    print("收到:", msg)
    if "e" in msg and msg["e"] == "depthUpdate":
        symbol = msg["s"]
        ts = msg["T"]
        # Aggregate liquidity from top10 depth
        try:
            bid_liq = _sum_liquidity(msg.get("b", []))
            ask_liq = _sum_liquidity(msg.get("a", []))
            _depth_liq_cache[symbol] = (bid_liq, ask_liq)
        except Exception as e:
            logging.warning(f"[WS] depth parse error: {e}")
            bid_liq, ask_liq = _depth_liq_cache.get(symbol, (0.0, 0.0))

        update_depth(symbol, {"bids": msg["b"], "asks": msg["a"]}, ts)
        # Feed detector：优先用 Redis price:binance（REST），缺失时用 _price_cache 或 depth 中间价
        try:
            if detector is not None:
                p = None
                try:
                    pv = redis_client.conn.hget(f"price:binance:{symbol}", "price")
                    if pv:
                        p = float(pv)
                except Exception:
                    pass
                if p is None and symbol in _price_cache:
                    p = _price_cache[symbol]
                if p is None:
                    bids, asks = msg.get("b", []), msg.get("a", [])
                    if bids and asks:
                        try:
                            p = (float(bids[0][0]) + float(asks[0][0])) / 2.0
                        except Exception:
                            pass
                if p is not None and p > 0:
                    ts_ms = int(float(ts)) if isinstance(ts, (int, float)) else int(time.time() * 1000)
                    asyncio.create_task(detector.add_tick_and_persist(symbol, p, bid_liq, ask_liq, ts_ms))
        except Exception as e:
            logging.warning(f"[WS] detector depth feed error: {e}")
    elif "e" in msg and msg["e"] == "aggTrade":
        symbol = msg["s"]
        # price:binance 由 REST ticker 定时任务写入，不再用 WS 价格（避免延迟）
        stream_key = f"aggtrades:binance:{symbol}"
        ts_raw = msg.get("T")
        ts_ms = int(float(ts_raw)) if isinstance(
            ts_raw, (int, float)) else int(time.time() * 1000)
        try:
            price_val = float(msg["p"]) if msg.get("p") is not None else None
        except Exception:
            price_val = None
        try:
            qty_val = float(msg["q"]) if msg.get("q") is not None else None
        except Exception:
            qty_val = None
        is_buyer_maker = bool(msg.get("m"))  # Binance 字段：买方是否为 maker

        if price_val is not None:
            # 将成交行为所需字段落入 Stream，供行为窗口聚合使用
            try:
                if qty_val is not None:
                    redis_client.xadd_stream(
                        stream_key,
                        {
                            "ts": ts_ms,
                            "price": price_val,
                            "qty": qty_val,
                            "is_buyer_maker": int(is_buyer_maker)
                        },
                        maxlen=50000,
                        approximate=True,
                        check_type=True,
                    )
            except Exception as e:
                logging.warning(
                    f"redis write error on XADD key={stream_key}: {e}")

            # Cache price and feed detector with latest depth liquidity
            try:
                _price_cache[symbol] = price_val
                bid_liq, ask_liq = _depth_liq_cache.get(symbol, (0.0, 0.0))
                if detector is not None:
                    asyncio.create_task(
                        detector.add_tick_and_persist(symbol, price_val,
                                                      bid_liq, ask_liq, ts_ms))
            except Exception as e:
                logging.warning(f"[WS] detector trade feed error: {e}")
    elif "e" in msg and msg["e"] == "forceOrder":
        await handle_force_order(msg)


async def main():
    """主程序"""
    ws = BinanceMarketWS(streams=[], on_message=on_msg)
    global detector

    try:
        await detector.start()
        await ws.start()
        t = threading.Thread(target=_rest_ticker_write_loop_thread, args=(0.8,), daemon=True)
        t.start()
        asyncio.create_task(monitor_symbols(ws))
        print("已启动")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logging.warning(f"[WS] error: {e}")
    finally:
        try:
            await ws.stop()
        except Exception:
            pass
        try:
            if detector is not None:
                await detector.stop()
        except Exception as e:
            logging.warning(f"[WS] detector stop error: {e}")
        # 刷新批量写入器，确保数据不丢失（同步方法，不需要 await）
        try:
            if redis_client._batch_writer:
                redis_client._batch_writer.flush()
                redis_client._batch_writer.close()
        except Exception as e:
            logging.warning(f"[WS] batch writer flush error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
    # _cleanup_symbol_keys("BTCUSDT")
