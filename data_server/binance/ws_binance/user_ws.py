import asyncio
from re import T
import traceback
import os
import logging

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
logger = logging.getLogger(__name__)


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
            snapshot_interval: int = 300,  # 仓位快照间隔（秒），默认5分钟
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws_url = ws_url
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        self.snapshot_interval = snapshot_interval
        self._ws = None
        self._running = False
        self._callback = None
        self._snapshot_task = None

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

    async def create_position_snapshot(self):
        """
        定期创建仓位快照，确保与交易所一致（借鉴NOFX）
        - 从WebSocket获取真实仓位
        - 对比Redis记录的仓位
        - 自动清理已平仓的仓位记录
        """
        try:
            # 获取当前仓位数据（从Redis，因为WebSocket已经在更新）
            from data_server.binance.ws_binance.utils.reids_connect import RedisClient
            redis_sync = RedisClient()
            positions_data = redis_sync.get_json("positions:binance")
            
            if not positions_data:
                logger.debug("仓位数据为空，跳过快照")
                return
            
            # 获取真实仓位（过滤掉数量为0的仓位）
            real_positions = positions_data if isinstance(positions_data, list) else []
            real_symbols = {
                p['symbol'] for p in real_positions 
                if float(p.get('positionAmt', 0)) != 0
            }
            
            # 从Redis获取记录的仓位
            recorded_symbols = redis_sync.conn.smembers("trading:open_positions:binance")
            recorded_symbols = {s.decode() if isinstance(s, bytes) else s for s in recorded_symbols}
            
            # 对比差异，清理已平仓的仓位
            for symbol in recorded_symbols:
                if symbol not in real_symbols:
                    redis_sync.conn.srem("trading:open_positions:binance", symbol)
                    logger.info(f"仓位快照：仓位已平仓，清理记录: {symbol}")
            
            # 更新Redis集合（确保所有真实仓位都在集合中）
            for symbol in real_symbols:
                redis_sync.conn.sadd("trading:open_positions:binance", symbol)
            
            logger.info(
                f"仓位快照完成: 真实仓位={len(real_symbols)}, "
                f"记录仓位={len(recorded_symbols)}, "
                f"清理={len(recorded_symbols - real_symbols)}"
            )
        except Exception as e:
            logger.error(f"仓位快照失败: {e}", exc_info=True)
    
    async def _snapshot_loop(self):
        """仓位快照循环任务"""
        while self._running:
            try:
                await asyncio.sleep(self.snapshot_interval)
                if self._running:
                    await self.create_position_snapshot()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"仓位快照循环错误: {e}", exc_info=True)
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def run(self):
        self._running = True
        # 启动仓位快照任务
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        
        while self._running:
            try:
                await self._connect()
            except Exception as e:
                print(f"❌ WS 连接错误: {e}, {self.reconnect_delay}秒后重连")
                await asyncio.sleep(self.reconnect_delay)

    async def stop(self):
        self._running = False
        
        # 停止仓位快照任务
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        
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
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ 错误: 请设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET")
        print("设置方式: export BINANCE_API_KEY=xxx BINANCE_API_SECRET=xxx")
        exit(1)

    # 检查是否使用测试网
    use_testnet = True

    
    if use_testnet:
        # Binance测试网WebSocket地址
        ws_url = "wss://testnet.binancefuture.com/ws-fapi/v1"
        print("🔶 使用测试网模式")
    else:
        # Binance实盘WebSocket地址
        ws_url = "wss://ws-fapi.binance.com/ws-fapi/v1"
        print("🔴 使用实盘模式")

    ws_client = BinanceUserWS(api_key=api_key, api_secret=api_secret, ws_url=ws_url)
    ws_client.register_callback(user_callback)

    asyncio.run(ws_client.run())
