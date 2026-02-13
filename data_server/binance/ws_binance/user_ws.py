import asyncio
import os
import traceback

import websockets
import json
import time
import hmac
import hashlib
from urllib.parse import urlencode
import ssl
from data_server.binance.ws_binance.utils.redis_client import get_async_redis
from data_server.binance.ws_binance.utils.binance_pos_analysis import BinanceAnalysisService

redis_client = get_async_redis()


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
            ws_url: str = "wss://ws-fapi.binance.com/ws-fapi/v1",
            ping_interval: int = 20,
            reconnect_delay: int = 5,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        self._ws = None
        self._running = False
        self._callback = None

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

    def _sign_params(self, params: dict) -> str:
        """HMAC-SHA256 签名"""
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method="v2/account.status"):
        timestamp = int(time.time() * 1000)
        params = {"apiKey": self.api_key, "timestamp": timestamp}
        signature = self._sign_params(params)
        params["signature"] = signature

        request = {
            "id": f"605a6d20-6588-4cb9-afa0-b0ab087507ba",
            "method": method,
            "params": params
        }
        return request

    async def _connect(self):
        async with websockets.connect(
                self.ws_url,
                ping_interval=20,  # 底层 WebSocket 自动 ping
                ssl=self.ssl_context
        ) as ws:
            self._ws = ws
            # 发送初始请求
            await ws.send(json.dumps(self._request("v2/account.status")))
            await ws.send(json.dumps(self._request("v2/account.position")))

            while self._running:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=4)  # 主动超时实现每秒请求
                    data = json.loads(message)
                    if self._callback:
                        if asyncio.iscoroutinefunction(self._callback):
                            await self._callback(data)
                        else:
                            self._callback(data)
                except asyncio.TimeoutError:
                    # 超时发送两个请求
                    await ws.send(json.dumps(self._request("v2/account.status")))
                    await ws.send(json.dumps(self._request("v2/account.position")))
                except websockets.ConnectionClosed as e:
                    print(f"⚠️ WS 已关闭: {e}")
                    break
                except Exception as e:
                    print(f"❌ 消息处理错误: {e}")

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                print(f"❌ WS 连接错误: {e}, {self.reconnect_delay}秒后重连")
                await asyncio.sleep(self.reconnect_delay)

    async def stop(self):
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


async def user_callback(data):
    result = data.get("result")
    if result is None:
        return

    # 情况 1: 持仓响应 (List) - 来自 v2/account.position
    if isinstance(result, list):
        positions = result
        print("持仓:", positions)
        try:
            BinanceAnalysisService().analysis(positions)
        except Exception as e:
            print(f"分析错误: {e}，{traceback.print_exc()}")

    # 情况 2: 状态响应 (Dict) - 来自 v2/account.status
    elif isinstance(result, dict):
        balance = result.get("totalMarginBalance")
        availableBalance = result.get("availableBalance")
        
        print("账户余额:", balance)
        print("账户可用余额:", availableBalance)
        try:
            await redis_client.set("balance:binance", json.dumps({"balance": balance, "availableBalance": availableBalance}))
        except Exception as e:
            print(f"Redis 写入错误: {e}")


if __name__ == "__main__":
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("错误: 请设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET")
        print("示例: export BINANCE_API_KEY=xxx  export BINANCE_API_SECRET=xxx")
        raise SystemExit(1)

    ws_client = BinanceUserWS(api_key=api_key, api_secret=api_secret)
    ws_client.register_callback(user_callback)

    asyncio.run(ws_client.run())
