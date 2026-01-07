import asyncio
import logging
import signal
import json
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow


class RouterFinalListener:
    FINAL_STREAM = "final_events"

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.final_stream = self.FINAL_STREAM
        self.group = "agent_final_router_group"
        self.consumer = "agent_final_router"

    @staticmethod
    def _j(s: str):
        """安全解析 JSON 字符串"""
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

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
            # 阻塞读取 Stream 消息
            res = await self.redis.xreadgroup(self.group, self.consumer, streams={self.final_stream: ">"}, count=50,
                                              block=5000)
            if not res:
                continue
            for _stream_name, entries in res:
                for entry_id, fields in entries:
                    # 1. 基础字段解析
                    ev = {k: (v if isinstance(v, str) else str(v)) for k, v in fields.items()}
                    
                    # 2. 解析嵌套的 JSON 结构 (meta, analysis_context, structure)
                    meta = self._j(ev.get("meta") or "{}")
                    ac = self._j(ev.get("analysis_context") or "{}")
                    st = self._j(ev.get("structure") or "{}")

                    # 3. 提取路由提示 (origin_source_hint)
                    # 该字段决定了事件的来源类型 (如 indicators, orderbook, liquidation 等)
                    hint = meta.get("origin_source_hint") or (ac.get("provenance") or {}).get(
                        "origin_source_hint") or "unknown"

                    # 4. 提取交易所信息 (exchange)
                    # 尝试从多个位置获取，如果没有明确指定，尝试从 account_id 或 source_event_id 推断
                    exchange = (ev.get("account_id").split("_")[0] or "").lower()
                    
                    if not exchange:
                        # 尝试从 source_event_id 解析 (例如: binance.BTCUSDT.trade... -> binance)
                        se_id = meta.get("source_event_id") or ""
                        if se_id:
                            exchange = (se_id.split(".")[0] or "").lower()

                    symbol = ev.get("symbol") or ""
                    fp = ev.get("final_priority") or "low"

                    # 5. 构建分发信息对象
                    info = {
                        "route": hint,  # 路由依据
                        "exchange": exchange or "",
                        "symbol": symbol,
                        "final_priority": fp,
                        "event_id": ev.get("event_id") or "",
                        "market_state": st.get("market_state"),
                        "direction": st.get("direction"),
                        "confidence": st.get("confidence"),
                        "confidence_numeric": st.get("confidence_numeric"),
                        "priority_weight": st.get("priority_weight"),
                        "l1_total_score": ac.get("l1_total_score"),
                        "tf_hint": ac.get("tf_hint"),
                    }

                    try:
                        print("[FinalRouter] dispatch", json.dumps(info, ensure_ascii=False))
                    except Exception:
                        print("[FinalRouter] dispatch", info)

                    # 6. 根据路由分发任务
                    # 目前仅处理 "indicators" 类型的信号，路由到 SignalValidationWorkflow
                    if info.get("symbol") and info.get("route") == "indicators":
                        wf = SignalValidationWorkflow()
                        # 异步启动工作流
                        asyncio.create_task(wf.arun(info))
                    elif info.get("symbol") and info.get("route") == "trade":
                        # 处理 trade 类型信号
                        is_short_term = meta.get("is_short_term") == True
                        
                        # 触发 TradeReviewWorkflow (示例)
                        # wf = TradeReviewWorkflow()
                        # asyncio.create_task(wf.arun(info, is_short_term=is_short_term))
                        pass
                    
                    # 确认消息已处理
                    await self.redis.xack(self.final_stream, self.group, entry_id)


async def _run():
    redis = aioredis.Redis(host=settings.redis_host, password=settings.redis_password, port=settings.redis_port,
                           db=settings.redis_db, decode_responses=True)
    listener = RouterFinalListener(redis)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        logging.getLogger("final").info("received_stop_signal")
        stop.set()

    loop.add_signal_handler(signal.SIGINT, _on_sig)
    loop.add_signal_handler(signal.SIGTERM, _on_sig)
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
        await redis.aclose()


def main():
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))
    asyncio.run(_run())


if __name__ == "__main__":
    main()
