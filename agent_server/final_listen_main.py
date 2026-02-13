import asyncio
import logging
import os
import signal
import json
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow
from agent_server.agent_workflow.trade_event_workflow import TradeEventWorkflow
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.utils.analysis_verifier import AnalysisVerifier
from agent_server.tools.price_fetcher import get_mark_price


class RouterFinalListener:
    FINAL_STREAM = "final_events"
    DEBUG = False

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.final_stream = self.FINAL_STREAM
        self.group = "agent_final_router_group"
        self.consumer = "agent_final_router"
        self.pending_min_idle_ms = int(os.environ.get("FINAL_PENDING_MIN_IDLE_MS", 10000))
        # 初始化事件记录器 (使用单例以共享连接池)
        self.event_recorder = get_recorder()
        # 初始化分析验证器 (复用 recorder 的 DB 和 Executor)
        self.analysis_verifier = AnalysisVerifier(
            self.event_recorder.db,
            self.event_recorder.executor
        )

    def _fire_and_forget(self, coro, name: str):
        task = asyncio.create_task(coro, name=name)

        def _done(t: asyncio.Task):
            try:
                exc = t.exception()
                if exc:
                    logging.getLogger("final").error(f"bg_task_failed: {name}: {exc}", exc_info=exc)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logging.getLogger("final").error(f"bg_task_callback_failed: {name}: {e}", exc_info=True)

        task.add_done_callback(_done)
        return task

    @staticmethod
    def _j(s: str):
        """安全解析 JSON 字符串"""
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    async def _autoclaim_pending(self, count: int = 50):
        try:
            # 中文注释：不同 redis-py 版本的 xautoclaim 返回值个数不同（可能是 2 或 3 个元素）
            # - (next_start_id, messages)
            # - (next_start_id, messages, deleted_ids)
            res = await self.redis.xautoclaim(
                self.final_stream,
                self.group,
                self.consumer,
                self.pending_min_idle_ms,
                "0-0",
                count=count,
            )
            if isinstance(res, (list, tuple)):
                if len(res) == 2:
                    _next_id, messages = res
                elif len(res) >= 3:
                    _next_id, messages, *_ = res
                else:
                    messages = []
            else:
                messages = []
            return messages or []
        except Exception as e:
            logging.getLogger("final").error(f"autoclaim_failed: {e}", exc_info=True)
            return []

    async def run(self):
        """
        监听 Redis Stream (final_events)，并根据路由提示分发到相应的工作流
        """
        try:
            # 尝试创建消费者组，如果已存在则忽略错误
            await self.redis.xgroup_create(self.final_stream, self.group, id="0", mkstream=True)
        except Exception:
            pass
        while True:
            # 优先回收/重试 pending 的消息，避免异常后消息卡在 PEL 里不再被 ">" 读取到
            entries = await self._autoclaim_pending(count=50)
            if not entries:
                # 阻塞读取 Stream 新消息
                res = await self.redis.xreadgroup(
                    self.group,
                    self.consumer,
                    streams={self.final_stream: ">"},
                    count=50,
                    block=5000,
                )
                if not res:
                    continue
                entries = []
                for _stream_name, batch in res:
                    entries.extend(batch)

            for entry_id, fields in entries:
                # 1. 基础字段解析
                ev = {k: (v if isinstance(v, str) else str(v)) for k, v in fields.items()}
                
                # 2. 解析嵌套的 JSON 结构 (meta, analysis_context, structure, trade_details)
                meta = self._j(ev.get("meta") or "{}")
                ac = self._j(ev.get("analysis_context") or "{}")
                st = self._j(ev.get("structure") or "{}")
                td = self._j(ev.get("trade_details") or "{}")

                # 3. 提取路由提示 (origin_source_hint)
                # 该字段决定了事件的来源类型 (如 indicators, orderbook, liquidation 等)
                hint = meta.get("origin_source_hint") or (ac.get("provenance") or {}).get(
                    "origin_source_hint") or "unknown"

                # 4. 提取交易所信息 (exchange)
                # 尝试从多个位置获取，如果没有明确指定，尝试从 account_id 或 source_event_id 推断
                account_id = ev.get("account_id") or ""
                exchange = account_id.split("_")[0].lower() if account_id else ""
                
                if not exchange:
                    # 尝试从 source_event_id 解析 (例如: binance.BTCUSDT.trade... -> binance)
                    se_id = meta.get("source_event_id") or ""
                    if se_id:
                        exchange = se_id.split(".")[0].lower()

                symbol = ev.get("symbol") or ""
                fp = ev.get("final_priority") or "low"
                event_type = ev.get("event_type") or ""

                # 5. 构建分发信息对象
                info = {
                    "route": hint,  # 路由依据
                    "exchange": exchange or "",
                    "symbol": symbol,
                    "final_priority": fp,
                    "event_id": ev.get("event_id") or "",
                    "event_type": event_type,
                    "timestamp": ev.get("timestamp"),
                    
                    # 分析数据
                    "market_state": st.get("market_state"),
                    "direction": st.get("direction"),
                    "confidence": st.get("confidence"),
                    "confidence_numeric": st.get("confidence_numeric"),
                    "priority_weight": st.get("priority_weight"),
                    "l1_total_score": ac.get("l1_total_score"),
                    "tf_hint": ac.get("tf_hint"),
                    "analysis_context": ac,
                    
                    # 完整数据 (供 recorder 和 price_fetcher 使用)
                    "meta": meta,
                    "trade_details": td,
                }

                try:
                    print("[FinalRouter] dispatch", json.dumps(info, ensure_ascii=False))
                except Exception:
                    print("[FinalRouter] dispatch", info)

                try:
                    # 6. 使用统一的 get_mark_price 组件获取价格
                    mark_price = await get_mark_price(info, exchange)

                    if info.get("symbol") and info.get("route") == "trade":
                        # 处理 trade 类型信号
                        raw_is_short = meta.get("is_short_term", False)
                        if isinstance(raw_is_short, str):
                            is_short_term = raw_is_short.lower() == "true"
                        else:
                            is_short_term = bool(raw_is_short)
                        info["is_short_term"] = is_short_term

                    # 7. 先确保行为性数据持久化成功，再确认消息，避免“最多一次”丢数据
                    saved = await self.event_recorder.save_event(info, mark_price)
                    if not saved:
                        logging.getLogger("final").error(
                            f"save_event_failed_skip_ack: entry_id={entry_id}, exchange={exchange}, symbol={symbol}"
                        )
                        continue

                    # 验证上一个事件的分析结果 (异步)
                    self._fire_and_forget(
                        self.analysis_verifier.verify_previous_analyses(info, mark_price),
                        name=f"verify_previous_analyses:{entry_id}",
                    )

                    # 8. 根据路由分发任务（异步，不阻塞 ack）
                    if not self.DEBUG:
                        if info.get("symbol") and info.get("route") in ["indicators", "mixed"]:
                            wf = SignalValidationWorkflow()
                            self._fire_and_forget(wf.arun(info), name=f"signal_validation:{entry_id}")
                        elif info.get("symbol") and info.get("route") == "trade":
                            wf = TradeEventWorkflow()
                            self._fire_and_forget(wf.arun(info), name=f"trade_event:{entry_id}")

                    # 确认消息已处理
                    await self.redis.xack(self.final_stream, self.group, entry_id)
                except Exception as e:
                    logging.getLogger("final").error(
                        f"handle_entry_failed_skip_ack: entry_id={entry_id}, err={e}", exc_info=True
                    )
                    continue


async def _run(stop_event: asyncio.Event = None):
    password = settings.redis_password
    if isinstance(password, str) and password.strip().lower() in ("none", "null", "undefined", ""):
        password = None
    # 中文注释：显式限制连接池，避免 Redis 端报 Too many connections
    max_connections = int(os.environ.get("REDIS_MAX_CONNECTIONS", 20))
    pool = aioredis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        decode_responses=True,
        max_connections=max_connections,
    )
    redis = aioredis.Redis(connection_pool=pool)
    listener = RouterFinalListener(redis)
    
    if stop_event is None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _on_sig(*_):
            logging.getLogger("final").info("received_stop_signal")
            stop.set()

        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    else:
        stop = stop_event
        
    task = asyncio.create_task(listener.run(), name="final_events_router")
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    finally:
        try:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            pass
        # 关闭全局 HTTPClient（如果本进程内使用过），避免退出时资源泄漏警告
        # 仅在独立运行时关闭
        if stop_event is None:
            from agent_server.utils.http_client import http_client

            await http_client.close()
        await redis.aclose()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
