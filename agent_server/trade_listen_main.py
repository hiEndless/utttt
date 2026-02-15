"""
交易决策监听服务 - 直接监听 l1_events，触发 SignalValidationWorkflow（含交易决策）
"""

import asyncio
import json
import logging
import os
import signal
from datetime import datetime

import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.tools.price_fetcher import get_mark_price_from_redis

TRADE_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(TRADE_LOG_DIR, exist_ok=True)

trade_logger = logging.getLogger("trade_decision")
trade_logger.setLevel(logging.INFO)
trade_logger.propagate = False
trade_handler = logging.FileHandler(
    os.path.join(TRADE_LOG_DIR, f"trade_decision_{datetime.now().strftime('%Y%m%d')}.log"),
    encoding="utf-8",
)
trade_handler.setFormatter(logging.Formatter("%(asctime)s [TRADE] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
trade_logger.addHandler(trade_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[TRADE] %(message)s"))
trade_logger.addHandler(console_handler)

# AI 推理过程日志 - 用于复盘
ai_reasoning_logger = logging.getLogger("trade_ai_reasoning")
ai_reasoning_logger.setLevel(logging.INFO)
ai_reasoning_logger.propagate = False
ai_reasoning_handler = logging.FileHandler(
    os.path.join(TRADE_LOG_DIR, f"trade_ai_reasoning_{datetime.now().strftime('%Y%m%d')}.log"),
    encoding="utf-8",
)
ai_reasoning_handler.setFormatter(logging.Formatter("%(asctime)s [AI_REASONING] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
ai_reasoning_logger.addHandler(ai_reasoning_handler)


class TradeL1Listener:
    """监听 l1_events stream，触发交易决策工作流"""

    L1_STREAM = "l1_events"
    DEDUP_TTL = int(os.environ.get("TRADE_L1_DEDUP_TTL", 300))  # 同一 event_id 去重秒数
    COOLDOWN_TTL = int(os.environ.get("TRADE_L1_COOLDOWN_TTL", 3))  # 同一 symbol 冷却秒数，默认 3
    MAX_CONCURRENT = int(os.environ.get("TRADE_L1_MAX_CONCURRENT", 8))  # 最大并发 workflow
    PENDING_MIN_IDLE_MS = int(os.environ.get("TRADE_L1_PENDING_MIN_IDLE_MS", 30000))  # 30s 未 ack 则回收

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.group = "trade_l1_group"
        self.consumer = "trade_l1_consumer"
        self.event_recorder = get_recorder()
        self.running_workflows = set()

    @staticmethod
    def _j(s):
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    async def _passes_dedup(self, event_id: str) -> bool:
        if not event_id:
            return True
        key = f"trade_l1:dedup:{event_id}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.DEDUP_TTL)
            return bool(ok)
        except Exception:
            return True

    async def _is_position_open(self, exchange: str, symbol: str) -> bool:
        try:
            return bool(await self.redis.sismember(f"trading:open_positions:{exchange}", symbol))
        except Exception:
            return False

    async def _passes_cooldown(self, symbol: str) -> bool:
        if not symbol:
            return True
        key = f"trade_l1:cooldown:{symbol}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.COOLDOWN_TTL)
            return bool(ok)
        except Exception:
            return True

    async def _startup_diagnostic(self) -> None:
        """启动时诊断 Redis 连接与 stream 状态"""
        try:
            stream_len = await self.redis.xlen(self.L1_STREAM)
            trade_logger.info(f"[诊断] stream={self.L1_STREAM} 当前消息数 XLEN={stream_len}")
            try:
                groups_info = await self.redis.xinfo_groups(self.L1_STREAM)
                for g in (groups_info or []):
                    g_name = g.get("name", "")
                    if isinstance(g_name, bytes):
                        g_name = g_name.decode()
                    last_id = g.get("last-delivered-id", "")
                    pending = g.get("pending", 0)
                    consumers = g.get("consumers", 0)
                    trade_logger.info(
                        f"[诊断] 消费组={g_name} last_id={last_id} pending={pending} consumers={consumers}"
                    )
            except Exception as ge:
                trade_logger.warning(f"[诊断] XINFO GROUPS 失败: {ge}")
            # 已开仓集合：来自 Redis SET trading:open_positions:{exchange}，推送 open 时加入、close 时移除
            try:
                for ex in ("binance",):
                    key = f"trading:open_positions:{ex}"
                    members = await self.redis.smembers(key)
                    if members:
                        syms = sorted(m.decode() if isinstance(m, bytes) else str(m) for m in members)
                        trade_logger.info(f"[诊断] {key} = {syms} (这些 symbol 的 L1 事件会被跳过)")
                    else:
                        trade_logger.info(f"[诊断] {key} = 空 (无已开仓 symbol)")
            except Exception as oe:
                trade_logger.warning(f"[诊断] 已开仓集合检查失败: {oe}")
        except Exception as e:
            trade_logger.error(f"[诊断] Redis 连接/stream 检查失败: {e}")

    @staticmethod
    def _fields_to_dict(fields) -> dict:
        """将 xreadgroup/xautoclaim 的 fields 转为 dict（兼容 list 格式）"""
        if isinstance(fields, dict):
            return {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in fields.items()}
        if isinstance(fields, (list, tuple)):
            d = {}
            for i in range(0, len(fields), 2):
                if i + 1 < len(fields):
                    k, v = fields[i], fields[i + 1]
                    d[k] = v.decode() if isinstance(v, bytes) else str(v)
            return d
        return {}

    async def _autoclaim_pending(self, count: int = 50) -> list:
        """回收超时未 ack 的 pending 消息，避免崩溃后卡在 PEL"""
        try:
            res = await self.redis.xautoclaim(
                self.L1_STREAM,
                self.group,
                self.consumer,
                self.PENDING_MIN_IDLE_MS,
                "0-0",
                count=count,
            )
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                messages = res[1]
                if messages:
                    trade_logger.info(f"[autoclaim] 回收 {len(messages)} 条超时 pending")
                return list(messages)
            return []
        except Exception as e:
            trade_logger.warning(f"[autoclaim] 失败: {e}")
            return []

    async def run(self):
        trade_logger.info(
            f"[启动] Redis host={settings.redis_host} port={settings.redis_port} db={settings.redis_db} "
            f"stream={self.L1_STREAM} group={self.group} "
            f"cooldown={self.COOLDOWN_TTL}s dedup={self.DEDUP_TTL}s max_concurrent={self.MAX_CONCURRENT}"
        )
        await self._startup_diagnostic()

        try:
            await self.redis.xgroup_create(self.L1_STREAM, self.group, id="0", mkstream=True)
            trade_logger.info(f"[启动] 消费组 {self.group} 已创建/已存在")
        except Exception as e:
            trade_logger.info(f"[启动] 消费组创建(可能已存在): {e}")

        trade_logger.info(f"开始监听 {self.L1_STREAM}...")
        _empty_read_count = 0

        while True:
            try:
                # 优先回收超时 pending，避免崩溃后消息卡在 PEL
                entries = await self._autoclaim_pending(count=50)
                if not entries:
                    res = await self.redis.xreadgroup(
                        self.group,
                        self.consumer,
                        streams={self.L1_STREAM: ">"},
                        count=50,
                        block=5000,
                    )
                    if not res:
                        _empty_read_count += 1
                        if _empty_read_count % 12 == 1 and _empty_read_count > 1:
                            trade_logger.info(f"[心跳] 持续监听中, 已 {_empty_read_count} 次 block 无新消息")
                        continue
                    entries = []
                    for _stream, batch in res:
                        entries.extend(batch)

                _empty_read_count = 0
                if entries:
                    trade_logger.info(f"[读取] 本批收到 {len(entries)} 条消息")
                for item in entries:
                    entry_id = item[0] if isinstance(item, (list, tuple)) else item
                    fields = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else {}
                    ev = self._fields_to_dict(fields)
                    symbol = ev.get("symbol", "").upper()
                    if not symbol:
                        trade_logger.debug(f"[跳过] 无symbol entry_id={entry_id}")
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue

                    exchange = "binance"
                    event_id = ev.get("event_id", "")
                    if event_id:
                        parts = event_id.split(".")
                        if parts:
                            exchange = parts[0].lower()

                    if not await self._passes_dedup(event_id):
                        trade_logger.info(f"[跳过] 去重 event_id={event_id} symbol={symbol}")
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue
                    if not await self._passes_cooldown(symbol):
                        trade_logger.info(f"[跳过] 冷却中 symbol={symbol} event_id={event_id}")
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue
                    if await self._is_position_open(exchange, symbol):
                        trade_logger.info(f"[跳过] 已开仓 symbol={symbol} event_id={event_id}")
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue
                    if len(self.running_workflows) >= self.MAX_CONCURRENT:
                        trade_logger.info(
                            f"[跳过] 并发已满({self.MAX_CONCURRENT}) symbol={symbol} "
                            f"event_id={event_id} running={list(self.running_workflows)[:3]}"
                        )
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue

                    total_score = float(ev.get("total_score", 0))
                    direction = ev.get("direction", "")
                    market_state = ev.get("market_state", "")
                    hint = ev.get("origin_source_hint", "indicators")
                    tf_hint = ["15m", "30m", "1h"]

                    info = {
                        "route": hint if hint in ("indicators", "mixed") else "indicators",
                        "exchange": exchange,
                        "symbol": symbol,
                        "final_priority": ev.get("result_priority", "low"),
                        "event_id": event_id,
                        "event_type": "l1_aggregated",
                        "timestamp": ev.get("timestamp", ""),
                        "market_state": market_state,
                        "direction": direction,
                        "confidence": "medium" if abs(total_score) >= 1.5 else "low",
                        "confidence_numeric": total_score,
                        "priority_weight": 10,
                        "l1_total_score": total_score,
                        "tf_hint": tf_hint,
                        "analysis_context": {
                            "l1_total_score": total_score,
                            "tf_hint": tf_hint,
                        },
                        "meta": {"origin_source_hint": hint, "source_event_id": event_id},
                        "trade_details": {},
                    }

                    trade_logger.info(f"收到L1事件 | {symbol} | direction={direction} | score={total_score}")

                    mark_price = await get_mark_price_from_redis(exchange, symbol)
                    if mark_price:
                        info["mark_price"] = mark_price

                    # 先入库再跑工作流，确保 save_agent_analysis 能找到事件
                    saved = await self.event_recorder.save_event(info, mark_price)
                    if not saved:
                        trade_logger.warning(f"L1 事件入库失败，跳过工作流: event_id={event_id}")
                        await self.redis.xack(self.L1_STREAM, self.group, entry_id)
                        continue

                    self.running_workflows.add(event_id)
                    wf = SignalValidationWorkflow()

                    async def _run_and_cleanup():
                        try:
                            await wf.arun(info)
                        finally:
                            self.running_workflows.discard(event_id)

                    asyncio.create_task(_run_and_cleanup())
                    await self.redis.xack(self.L1_STREAM, self.group, entry_id)

            except Exception as e:
                trade_logger.error(f"处理事件出错: {e}")
                await asyncio.sleep(1)


async def _run():
    password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    max_conn = int(os.environ.get("REDIS_MAX_CONNECTIONS", 20))
    pool = aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
        max_connections=max_conn,
    )
    redis_client = aioredis.Redis(connection_pool=pool)
    listener = TradeL1Listener(redis_client)
    stop = asyncio.Event()

    def _on_sig(*_):
        trade_logger.info("收到停止信号")
        stop.set()

    try:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        import sys
        signal.signal(signal.SIGINT, lambda s, f: stop.set())
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, lambda s, f: stop.set())

    task = asyncio.create_task(listener.run(), name="trade_l1_listener")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await redis_client.aclose()
        trade_logger.info("Trade L1 Listener 已停止")


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("agno").setLevel(logging.CRITICAL)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
