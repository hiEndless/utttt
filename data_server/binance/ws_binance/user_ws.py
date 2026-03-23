import asyncio
import os
import traceback
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
from agent_server.utils.trade_push import push_trade_to_redis

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

redis_client = get_async_redis()
analysis_service = BinanceAnalysisService()
logger = logging.getLogger("position_guardian")
guardian = None


class PositionGuardian:
    """
    智能仓位守护：
    1) 硬止损（MAE 控制）
    2) 浮盈回撤保护（Trailing Stop）
    3) 可选 LLM 二次判断（失败回退规则）
    """

    def __init__(self, api_key: str, api_secret: str, use_testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://testnet.binancefuture.com" if use_testnet else "https://fapi.binance.com"
        self.enabled = os.getenv("POSITION_GUARDIAN_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
        self.use_llm = os.getenv("POSITION_GUARDIAN_USE_LLM", "false").strip().lower() in ("1", "true", "yes", "on")
        self.stop_loss_ratio = float(os.getenv("POSITION_GUARDIAN_STOP_LOSS_RATIO", "-0.15"))  # -15%
        self.take_profit_arm = float(os.getenv("POSITION_GUARDIAN_TAKE_PROFIT_ARM", "0.02"))   # +2% 后启动跟踪
        self.trailing_drawdown = float(os.getenv("POSITION_GUARDIAN_TRAILING_DRAWDOWN", "0.012"))  # 回撤 1.2% 触发
        self.min_hold_seconds = int(os.getenv("POSITION_GUARDIAN_MIN_HOLD_SECONDS", "30"))
        self.cooldown_seconds = int(os.getenv("POSITION_GUARDIAN_COOLDOWN_SECONDS", "20"))
        self._peak_pnl_ratio = {}   # key: symbol:side -> peak pnl ratio
        self._last_action_ts = {}   # key: symbol:side -> ts
        self._llm_client = None
        self._llm_model = os.getenv("POSITION_GUARDIAN_LLM_MODEL", "qwen-plus-character")
        self._llm_base = os.getenv("POSITION_GUARDIAN_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self._llm_key = os.getenv("POSITION_GUARDIAN_LLM_API_KEY", "")
        if self.use_llm and OpenAI and self._llm_key:
            try:
                self._llm_client = OpenAI(base_url=self._llm_base, api_key=self._llm_key, timeout=8.0)
            except Exception as e:
                logger.warning(f"[Guardian] LLM client init failed: {e}")
                self._llm_client = None

    @staticmethod
    def _to_float(v, default=0.0):
        try:
            return float(str(v))
        except Exception:
            return default

    @staticmethod
    def _key(pos: dict) -> str:
        return f"{pos.get('symbol','')}:{pos.get('positionSide','')}"

    def _sign(self, params: dict) -> str:
        query_string = urlencode(sorted(params.items()))
        return hmac.new(self.api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _build_close_trade_json(pos: dict, qty: float, reason: str) -> dict:
        symbol = str(pos.get("symbol") or "")
        position_side = str(pos.get("positionSide") or "LONG").upper()
        side = "SELL" if position_side == "LONG" else "BUY"
        mark_price = PositionGuardian._to_float(pos.get("markPrice"), 0.0)
        leverage = max(1.0, PositionGuardian._to_float(pos.get("leverage"), 1.0))
        q = f"{qty:.8f}".rstrip("0").rstrip(".")
        if not q:
            q = "0"
        return {
            "order_type": "close",
            "symbol": symbol,
            "exchange": "binance",
            "positionSide": position_side,
            "side": side,
            "leverage": leverage,
            "sums": q,
            "quantity": q,
            "openAvgPx": mark_price,
            "task_id": 23,
            "user_id": 2,
            "api_id": 0,
            "trade_trigger_mode": 0,
            "tp_trigger_px": 0,
            "sl_trigger_px": 0,
            "acc": {
                "key": "",
                "secret": "",
                "passphrase": "",
                "proxies": {},
                "exchange": 2,
            },
            "flag": "1",
            "uniqueName": "position_guardian",
            "guardian_reason": reason,
            "guardian_ts": int(time.time() * 1000),
        }

    def _rule_decision(self, pos: dict, pnl_ratio: float, peak: float, age_s: float) -> tuple[bool, str]:
        if age_s < self.min_hold_seconds:
            return False, f"持仓未达最短观察期 age={age_s:.1f}s"
        if pnl_ratio <= self.stop_loss_ratio:
            return True, f"触发止损 pnl_ratio={pnl_ratio:.4f} <= {self.stop_loss_ratio:.4f}"
        if peak >= self.take_profit_arm and (peak - pnl_ratio) >= self.trailing_drawdown:
            return True, (
                f"触发浮盈回撤保护 peak={peak:.4f}, now={pnl_ratio:.4f}, "
                f"dd={peak - pnl_ratio:.4f} >= {self.trailing_drawdown:.4f}"
            )
        return False, "规则未触发"

    def _llm_decision(self, pos: dict, pnl_ratio: float, peak: float, age_s: float) -> tuple[bool, str]:
        if not self._llm_client:
            return False, "LLM未启用"
        try:
            prompt = {
                "task": "position_guardian",
                "goal": "资金保护优先，先保本后扩利，只允许 HOLD 或 FULL_CLOSE",
                "position": {
                    "symbol": pos.get("symbol"),
                    "positionSide": pos.get("positionSide"),
                    "positionAmt": pos.get("positionAmt"),
                    "entryPrice": pos.get("entryPrice"),
                    "markPrice": pos.get("markPrice"),
                    "unRealizedProfit": pos.get("unRealizedProfit"),
                    "pnl_ratio": pnl_ratio,
                    "peak_pnl_ratio": peak,
                    "age_seconds": age_s,
                },
                "risk_rules": {
                    "stop_loss_ratio": self.stop_loss_ratio,
                    "take_profit_arm": self.take_profit_arm,
                    "trailing_drawdown": self.trailing_drawdown,
                    "min_hold_seconds": self.min_hold_seconds,
                },
                "output": {"action": "HOLD|FULL_CLOSE", "reason": "string"},
            }
            r = self._llm_client.chat.completions.create(
                model=self._llm_model,
                messages=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                max_tokens=120,
                temperature=0,
            )
            txt = (r.choices[0].message.content or "").strip()
            data = json.loads(txt) if txt.startswith("{") else {"action": "HOLD", "reason": txt}
            action = str(data.get("action", "HOLD")).upper()
            reason = str(data.get("reason", ""))
            return action == "FULL_CLOSE", f"LLM:{reason}"
        except Exception as e:
            return False, f"LLM异常回退规则: {e}"

    async def on_positions(self, positions: list):
        if not self.enabled:
            return
        now = time.time()
        for pos in positions or []:
            amt = self._to_float(pos.get("positionAmt"), 0.0)
            if amt == 0.0:
                continue
            key = self._key(pos)
            last_ts = self._last_action_ts.get(key, 0)
            if now - last_ts < self.cooldown_seconds:
                continue
            update_ms = self._to_float(pos.get("updateTime"), now * 1000)
            age_s = max(0.0, now - (update_ms / 1000.0))
            up = self._to_float(pos.get("unRealizedProfit"), 0.0)
            im = self._to_float(pos.get("initialMargin"), 0.0)
            pnl_ratio = (up / im) if im > 0 else 0.0
            peak = self._peak_pnl_ratio.get(key, pnl_ratio)
            peak = max(peak, pnl_ratio)
            self._peak_pnl_ratio[key] = peak

            should_close, reason = self._rule_decision(pos, pnl_ratio, peak, age_s)
            if not should_close and self.use_llm:
                llm_close, llm_reason = self._llm_decision(pos, pnl_ratio, peak, age_s)
                if llm_close:
                    should_close, reason = True, llm_reason
                else:
                    reason = llm_reason if "异常" in llm_reason else reason

            if should_close:
                qty = abs(amt)
                symbol = str(pos.get("symbol"))
                pside = str(pos.get("positionSide", "LONG")).upper()
                try:
                    trade_json = self._build_close_trade_json(pos, qty, reason)
                    result = await push_trade_to_redis(trade_json)
                    self._last_action_ts[key] = now
                    logger.warning(
                        f"[Guardian] 已推送平仓任务 symbol={symbol} side={pside} qty={qty} reason={reason} pushed={result}"
                    )
                except Exception as e:
                    logger.error(
                        f"[Guardian] 平仓任务推送失败 symbol={symbol} side={pside} qty={qty} reason={reason} err={e}"
                    )


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
        # 临时去掉代理相关环境变量，强制直连（避免 ALL_PROXY / HTTPS_PROXY 等导致走代理）
        _saved = {}
        for _k in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "WSS_PROXY", "wss_proxy", "WS_PROXY", "ws_proxy"):
            if _k in os.environ:
                _saved[_k] = os.environ.pop(_k)
        try:
            async with websockets.connect(
                    self.ws_url,
                    ping_interval=20,  # 底层 WebSocket 自动 ping
                    ssl=self.ssl_context,
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
        finally:
            for _k, _v in _saved.items():
                os.environ[_k] = _v

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
            analysis_service.analysis(positions)
        except Exception as e:
            print(f"分析错误: {e}，{traceback.print_exc()}")
        try:
            if guardian is not None:
                await guardian.on_positions(positions)
        except Exception as e:
            print(f"Guardian 错误: {e}")

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


def _is_testnet() -> bool:
    """从环境变量读取是否使用模拟盘（测试网）。默认 True=模拟盘。"""
    v = os.getenv("BINANCE_TESTNET", "true").strip().lower()
    return v in ("1", "true", "yes", "on")


if __name__ == "__main__":
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("错误: 请设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET")
        print("示例: export BINANCE_API_KEY=xxx  export BINANCE_API_SECRET=xxx")
        raise SystemExit(1)

    use_testnet = _is_testnet()
    if use_testnet:
        ws_url = "wss://testnet.binancefuture.com/ws-fapi/v1"
        print("🔶 使用模拟盘（测试网）")
    else:
        ws_url = "wss://ws-fapi.binance.com/ws-fapi/v1"
        print("🔴 使用实盘")

    ws_client = BinanceUserWS(api_key=api_key, api_secret=api_secret, ws_url=ws_url)
    ws_client.register_callback(user_callback)
    guardian = PositionGuardian(api_key=api_key, api_secret=api_secret, use_testnet=use_testnet)

    asyncio.run(ws_client.run())
