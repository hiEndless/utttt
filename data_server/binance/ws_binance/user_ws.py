import os
import sys

if __name__ == "__main__" and __package__ is None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "../../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.abspath(os.path.join(base_dir, "../.env")))
    except Exception:
        pass

import asyncio
import traceback
import uuid
import inspect

import websockets
import json
import time
import hmac
import hashlib
from urllib.parse import urlencode
import ssl
from data_server.binance.ws_binance.utils.redis_client import get_async_redis
from data_server.binance.ws_binance.utils.binance_pos_analysis import BinanceAnalysisService

analysis_service = BinanceAnalysisService()


class ExchangeSession:
    """
    中文注释：单个交易所账号的一次 WS 会话（连接 + 监听 + 周期请求）。
    - 负责资源生命周期：start/stop
    - 负责内部任务：listen_task/request_task
    - 连接异常/任务异常交由上层 BinanceUserWS 负责重连
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        ws_url: str,
        ssl_context: ssl.SSLContext,
        request_interval_s: float = 4.0,
        callback=None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url
        self.ssl_context = ssl_context
        self.request_interval_s = float(request_interval_s)
        self.callback = callback

        self.ws = None
        self.running = False
        self.listen_task: asyncio.Task | None = None
        self.request_task: asyncio.Task | None = None

    def _sign_params(self, params: dict) -> str:
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _build_request(self, method: str) -> dict:
        timestamp = int(time.time() * 1000)
        params = {"apiKey": self.api_key, "timestamp": timestamp}
        params["signature"] = self._sign_params(params)
        return {
            "id": uuid.uuid4().hex,
            "method": method,
            "params": params,
        }

    async def _connect(self):
        return await websockets.connect(
            self.ws_url,
            ping_interval=20,
            ssl=self.ssl_context,
            max_queue=None,
        )

    async def start(self) -> None:
        self.running = True
        self.ws = await self._connect()

        # 中文注释：先发一次请求，避免等到第一个周期才有数据。
        await self._safe_send(self._build_request("v2/account.status"))
        await self._safe_send(self._build_request("v2/account.position"))

        self.listen_task = asyncio.create_task(self._listen())
        self.request_task = asyncio.create_task(self._request_loop())

    async def stop(self) -> None:
        self.running = False

        tasks = [t for t in [self.listen_task, self.request_task] if t is not None]
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        self.listen_task = None
        self.request_task = None

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    async def wait(self) -> None:
        tasks = [t for t in [self.listen_task, self.request_task] if t is not None]
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for d in done:
            exc = d.exception()
            if exc:
                raise exc
        for p in pending:
            try:
                await p
            except asyncio.CancelledError:
                pass

    async def _safe_send(self, payload: dict) -> None:
        if not self.ws or not self.running:
            return
        try:
            await self.ws.send(json.dumps(payload))
        except Exception:
            raise

    async def _request_loop(self) -> None:
        try:
            while self.running:
                await asyncio.sleep(self.request_interval_s)
                await self._safe_send(self._build_request("v2/account.status"))
                await self._safe_send(self._build_request("v2/account.position"))
        except asyncio.CancelledError:
            pass

    async def _listen(self) -> None:
        try:
            async for msg in self.ws:
                if not self.running:
                    break
                await self._handle(msg)
        except asyncio.CancelledError:
            pass

    async def _handle(self, msg: str) -> None:
        try:
            data = json.loads(msg)
        except Exception:
            return
        if not self.callback:
            return
        if inspect.iscoroutinefunction(self.callback):
            await self.callback(data)
        else:
            self.callback(data)


class BinanceUserWS:
    """
    Binance USDT-M Futures 用户信息 WebSocket
    - 使用官方 API Key + Secret 做 HMAC-SHA256 签名
    - 自动重连 + 心跳 ping/pong
    - 异常捕获与 SSL 容错
    """

    def __init__(
            self,
            api_key: str,
            api_secret: str,
            user_id: str | None = None,
            exchange_account_id: str | None = None,
            ws_url: str = "wss://ws-fapi.binance.com/ws-fapi/v1",
            ping_interval: int = 20,
            reconnect_delay: int = 5,
            request_interval_s: float = 4.0,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = str(user_id).strip() if user_id else None
        self.exchange_account_id = str(exchange_account_id).strip() if exchange_account_id else None
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        self.request_interval_s = float(request_interval_s)
        self._ws = None
        self._running = False
        self._callback = None
        self._session: ExchangeSession | None = None

        # SSL context（可解决 self-signed 证书问题）
        self.ssl_context = ssl.create_default_context()
        # 测试环境可暂时禁用证书验证
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        

    def register_callback(self, cb):
        """
        注册消息回调
        cb(data: dict)
        """
        self._callback = cb

    async def run(self):
        self._running = True
        try:
            analysis_service.set_account_context(self.user_id, self.exchange_account_id)
        except Exception:
            pass
        while self._running:
            try:
                self._session = ExchangeSession(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    ws_url=self.ws_url,
                    ssl_context=self.ssl_context,
                    request_interval_s=self.request_interval_s,
                    callback=self._callback,
                )
                await self._session.start()
                await self._session.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ WS 连接错误: {e}, {self.reconnect_delay}秒后重连")
            finally:
                if self._session:
                    try:
                        await self._session.stop()
                    except Exception:
                        pass
                    self._session = None
                self._ws = None
            if self._running:
                await asyncio.sleep(self.reconnect_delay)

    async def stop(self):
        self._running = False
        if self._session:
            try:
                await self._session.stop()
            except Exception:
                pass
            self._session = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        try:
            analysis_service.set_account_context(None, None)
        except Exception:
            pass


async def user_callback(data):
    result = data.get("result")
    if result is None:
        return

    # 情况 1: 持仓响应 (List) - 来自 v2/account.position
    if isinstance(result, list):
        positions = result
        print("持仓:", positions)
        try:
            analysis_service.analysis(positions)
        except Exception as e:
            print(f"分析错误: {e}，{traceback.print_exc()}")

    # 情况 2: 状态响应 (Dict) - 来自 v2/account.status
    elif isinstance(result, dict):
        balance = result.get("totalMarginBalance")
        availableBalance = result.get("availableBalance")
        
        print("账户余额:", balance)
        print("账户可用余额:", availableBalance)
        try:
            redis_client = get_async_redis()
            await redis_client.set("balance:binance", json.dumps({"balance": balance, "availableBalance": availableBalance}))
        except Exception as e:
            print(f"Redis 写入错误: {e}")


if __name__ == "__main__":
    import os
    import signal

    def _load_from_env():
        api_key = str(os.getenv("BINANCE_API_KEY", "") or "").strip()
        api_secret = str(os.getenv("BINANCE_API_SECRET", "") or "").strip()
        if api_key and api_secret:
            return api_key, api_secret, None, None
        return None

    async def _load_from_redis(redis_client):
        try:
            raw = await redis_client.get("exchange_account:binance:active")
        except Exception:
            return None
        if not raw:
            return None
        try:
            obj = json.loads(raw)
        except Exception:
            return None
        api_key = str(obj.get("api_key") or "").strip()
        api_secret = str(obj.get("api_secret") or "").strip()
        user_id = str(obj.get("user_id") or "").strip()
        exchange_account_id = str(obj.get("exchange_account_id") or "").strip()
        if api_key and api_secret and user_id and exchange_account_id:
            return api_key, api_secret, user_id, exchange_account_id
        return None

    async def _standalone_main():
        stop_evt = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _on_stop(*_):
            stop_evt.set()

        try:
            loop.add_signal_handler(signal.SIGINT, _on_stop)
            loop.add_signal_handler(signal.SIGTERM, _on_stop)
        except Exception:
            pass

        poll_s = float(os.getenv("EXCHANGE_ACTIVE_WATCH_INTERVAL_S", "1.0") or "1.0")
        current = None
        ws_client: BinanceUserWS | None = None
        ws_task: asyncio.Task | None = None
        redis_client = get_async_redis()
        print(f"[user_ws] watching exchange_account:binance:active redis_db={os.getenv('REDIS_DB', '')} redis_host={os.getenv('REDIS_HOST', '')} redis_port={os.getenv('REDIS_PORT', '')}")

        try:
            while not stop_evt.is_set():
                cfg = await _load_from_redis(redis_client)
                if cfg is None:
                    cfg = _load_from_env()

                if cfg != current:
                    current = cfg
                    if ws_task:
                        ws_task.cancel()
                        try:
                            await ws_task
                        except asyncio.CancelledError:
                            pass
                        except Exception:
                            pass
                        ws_task = None
                    if ws_client:
                        try:
                            await ws_client.stop()
                        except Exception:
                            pass
                        ws_client = None

                    if cfg:
                        api_key, api_secret, user_id, exchange_account_id = cfg
                        ws_client = BinanceUserWS(
                            api_key=api_key,
                            api_secret=api_secret,
                            user_id=user_id,
                            exchange_account_id=exchange_account_id,
                        )
                        ws_client.register_callback(user_callback)
                        ws_task = asyncio.create_task(ws_client.run())
                        print("[user_ws] config applied, ws task started")
                    else:
                        print("[user_ws] config cleared, ws stopped")

                await asyncio.sleep(max(0.2, poll_s))
        finally:
            if ws_task:
                ws_task.cancel()
                try:
                    await ws_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            if ws_client:
                try:
                    await ws_client.stop()
                except Exception:
                    pass
            try:
                await redis_client.aclose()
            except Exception:
                pass

    asyncio.run(_standalone_main())
