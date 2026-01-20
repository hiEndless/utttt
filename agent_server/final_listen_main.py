import asyncio
import logging
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
        # 初始化事件记录器 (使用单例以共享连接池)
        self.event_recorder = get_recorder()
        # 初始化分析验证器 (复用 recorder 的 DB 和 Executor)
        self.analysis_verifier = AnalysisVerifier(
            self.event_recorder.db,
            self.event_recorder.executor
        )

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

                    # 6. 异步入库事件（不阻塞后续处理）
                    # 使用统一的 get_mark_price 组件获取价格
                    mark_price = await get_mark_price(info, exchange)
                    
                    # 创建入库任务（不等待结果，避免阻塞）
                    asyncio.create_task(self.event_recorder.save_event(info, mark_price))
                    
                    # 验证上一个事件的分析结果 (异步)
                    asyncio.create_task(self.analysis_verifier.verify_previous_analyses(info, mark_price))
                    
                    # 7. 根据路由分发任务
                    if not self.DEBUG:
                        if info.get("symbol") and info.get("route") == "indicators":
                            wf = SignalValidationWorkflow()
                            # 异步启动工作流
                            asyncio.create_task(wf.arun(info))
                        elif info.get("symbol") and info.get("route") == "trade":
                            # 处理 trade 类型信号
                            raw_is_short = meta.get("is_short_term", False)
                            if isinstance(raw_is_short, str):
                                is_short_term = raw_is_short.lower() == "true"
                            else:
                                is_short_term = bool(raw_is_short)
                            info["is_short_term"] = is_short_term
                                
                            wf = TradeEventWorkflow()
                            asyncio.create_task(wf.arun(info))
                    
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
