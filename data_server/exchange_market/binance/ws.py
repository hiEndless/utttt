import asyncio
import json
import websockets
import logging
import ssl
import time

from data_server.exchange_market.binance.utils.reids_connect import RedisClient
from data_server.exchange_market.binance.utils.spike_trigger import SpikeDetector

redis_client = RedisClient()

# ---- SpikeDetector integration state ----
detector = SpikeDetector()
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


class BinanceFuturesWS:
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
                await ws.add_stream(f"{sym.lower()}@depth10@100ms")
                active_symbols.add(sym)

            # 移除订阅
            for sym in active_symbols - symbols:
                print("移除订阅:", symbols)
                await ws.remove_stream(f"{sym.lower()}@aggTrade")
                await ws.remove_stream(f"{sym.lower()}@depth10@100ms")
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

        redis_client.update_depth(symbol, {
            "bids": msg["b"],
            "asks": msg["a"]
        }, ts)
        # Feed detector using latest price cache if available
        try:
            if detector is not None and symbol in _price_cache:
                p = _price_cache[symbol]
                ts_sec = float(ts) / 1000.0 if isinstance(ts, (int, float)) else None
                asyncio.create_task(detector.add_tick_and_persist(symbol, p, bid_liq, ask_liq, ts_sec))
        except Exception as e:
            logging.warning(f"[WS] detector depth feed error: {e}")
    elif "e" in msg and msg["e"] == "aggTrade":
        symbol = msg["s"]
        # Consolidate price/ts extraction, then write hash and feed detector
        key = f"price:binance:{symbol}"
        ts_raw = msg.get("T")
        ts_sec = float(ts_raw) / 1000.0 if isinstance(ts_raw, (int, float)) else time.time()
        try:
            price_val = float(msg["p"]) if msg.get("p") is not None else None
        except Exception:
            price_val = None

        if price_val is not None:
            # Update price in Redis as hash via RedisClient
            try:
                redis_client.set_hash(key, {"ts": ts_sec, "price": price_val}, check_type=True)
            except Exception as e:
                logging.warning(f"redis write error on HSET key={key}: {e}")

            # Cache price and feed detector with latest depth liquidity
            try:
                _price_cache[symbol] = price_val
                bid_liq, ask_liq = _depth_liq_cache.get(symbol, (0.0, 0.0))
                if detector is not None:
                    asyncio.create_task(detector.add_tick_and_persist(symbol, price_val, bid_liq, ask_liq, ts_sec))
            except Exception as e:
                logging.warning(f"[WS] detector trade feed error: {e}")


async def main():
    """主程序"""
    ws = BinanceFuturesWS(
        streams=[],
        on_message=on_msg
    )
    global detector

    try:
        await detector.start()
        await ws.start()
        print("已启动")
        asyncio.create_task(monitor_symbols(ws))
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
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
