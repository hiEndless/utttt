import asyncio
import logging
import signal
import json
import os
from datetime import datetime
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.agent_workflow.signal_validation_workflow import SignalValidationWorkflow
from agent_server.utils.trade_event_recorder import get_recorder
from agent_server.utils.price_fetcher import get_mark_price_from_redis

# 配置独立的 trade 日志
TRADE_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(TRADE_LOG_DIR, exist_ok=True)

trade_logger = logging.getLogger("trade_decision")
trade_logger.setLevel(logging.INFO)
trade_logger.propagate = False  # 不传播到根 logger

# 文件日志
trade_handler = logging.FileHandler(
    os.path.join(TRADE_LOG_DIR, f"trade_decision_{datetime.now().strftime('%Y%m%d')}.log"),
    encoding='utf-8'
)
trade_handler.setFormatter(
    logging.Formatter('%(asctime)s [TRADE] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
)
trade_logger.addHandler(trade_handler)

# 控制台日志（简化格式）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('[TRADE] %(message)s'))
trade_logger.addHandler(console_handler)


class TradeL1Listener:
    """
    直接监听 l1_events stream，处理所有币种
    并触发交易决策工作流
    """
    L1_STREAM = "l1_events"
    DEBUG = True

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.l1_stream = self.L1_STREAM
        self.group = "trade_l1_group"
        self.consumer = "trade_l1_consumer"
        self.event_recorder = get_recorder()
        
        # 去重和冷却期配置
        self.dedup_ttl = 300  # 5分钟内不重复处理相同 event_id
        self.cooldown_ttl = 10  # 10秒内不重复处理相同 symbol 的事件
        self.max_concurrent_workflows = 3  # 最大并发工作流数
        self.running_workflows = set()  # 正在运行的工作流 event_id
        
        trade_logger.info(f"=== Trade L1 Listener 启动 ===")
        trade_logger.info(f"监听流: {self.l1_stream}")
        trade_logger.info(f"处理模式: 所有币种")
        trade_logger.info(f"去重TTL: {self.dedup_ttl}秒 | 冷却期: {self.cooldown_ttl}秒 | 最大并发: {self.max_concurrent_workflows}")
        log_file = os.path.join(TRADE_LOG_DIR, f'trade_decision_{datetime.now().strftime("%Y%m%d")}.log')
        print(f"\n{'='*60}")
        print(f"[TradeListener] 启动成功")
        print(f"  监听流: {self.l1_stream}")
        print(f"  处理模式: 所有币种")
        print(f"  日志文件: {log_file}")
        print(f"  去重TTL: {self.dedup_ttl}秒 | 冷却期: {self.cooldown_ttl}秒")
        print(f"{'='*60}\n")

    @staticmethod
    def _j(s: str):
        """安全解析 JSON 字符串"""
        try:
            return json.loads(s) if s else {}
        except Exception:
            return {}

    def _log_trade_event(self, event_type: str, symbol: str, data: dict):
        """记录交易事件到日志文件和 Redis"""
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "symbol": symbol,
                "data": data
            }
            
            # 写入日志文件
            trade_logger.info(f"{event_type} | {symbol} | {json.dumps(data, ensure_ascii=False)}")
            
            # 存储到 Redis
            asyncio.create_task(self._save_to_redis(symbol, log_data))
        except Exception as e:
            print(f"[TradeListener] 日志记录失败: {e}")

    async def _save_to_redis(self, symbol: str, log_data: dict):
        """将分析过程存储到 Redis"""
        try:
            rc = self.redis
            key = f"trade:analysis:{symbol}:{datetime.now().strftime('%Y%m%d')}"
            # 使用 list 存储，保留最近 1000 条
            await rc.lpush(key, json.dumps(log_data, ensure_ascii=False))
            await rc.ltrim(key, 0, 999)  # 只保留最近 1000 条
            await rc.expire(key, 86400 * 7)  # 7 天过期
        except Exception as e:
            print(f"[TradeListener] Redis 存储失败: {e}")

    async def _passes_dedup(self, event_id: str) -> bool:
        """检查事件是否已处理过（去重）"""
        if not event_id:
            return True
        key = f"trade_l1:dedup:{event_id}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.dedup_ttl)
            return ok is True
        except Exception as e:
            trade_logger.debug(f"去重检查失败: {e}")
            return True  # 出错时允许处理，避免阻塞

    async def _passes_cooldown(self, symbol: str) -> bool:
        """检查是否在冷却期内（防止短时间内重复处理）"""
        if not symbol:
            return True
        key = f"trade_l1:cooldown:{symbol}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.cooldown_ttl)
            return ok is True
        except Exception as e:
            trade_logger.debug(f"冷却期检查失败: {e}")
            return True  # 出错时允许处理

    async def run(self):
        """监听 l1_events stream，处理所有币种并触发交易决策"""
        try:
            await self.redis.xgroup_create(self.l1_stream, self.group, id="0", mkstream=True)
        except Exception:
            pass
        
        trade_logger.info(f"开始监听 {self.l1_stream} stream...")
        
        while True:
            try:
                # 阻塞读取 Stream 消息
                res = await self.redis.xreadgroup(
                    self.group, 
                    self.consumer, 
                    streams={self.l1_stream: ">"}, 
                    count=50,
                    block=5000
                )
                
                if not res:
                    continue
                
                for _stream_name, entries in res:
                    for entry_id, fields in entries:
                        # 解析事件
                        ev = {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in fields.items()}
                        
                        symbol = ev.get("symbol", "").upper()
                        
                        # 跳过没有 symbol 的事件
                        if not symbol:
                            await self.redis.xack(self.l1_stream, self.group, entry_id)
                            continue
                        
                        # 构建事件信息（转换为 final_event 格式以便复用工作流）
                        exchange = "binance"  # 默认，可以从 event_id 解析
                        event_id = ev.get("event_id", "")
                        if event_id:
                            parts = event_id.split(".")
                            if len(parts) > 0:
                                exchange = parts[0].lower()
                        
                        # 去重检查：如果已处理过，跳过
                        if not await self._passes_dedup(event_id):
                            trade_logger.debug(f"跳过重复事件 | {symbol} | event_id={event_id}")
                            await self.redis.xack(self.l1_stream, self.group, entry_id)
                            continue
                        
                        # 冷却期检查：如果 symbol 在冷却期内，跳过
                        if not await self._passes_cooldown(symbol):
                            trade_logger.debug(f"跳过冷却期内事件 | {symbol} | event_id={event_id}")
                            await self.redis.xack(self.l1_stream, self.group, entry_id)
                            continue
                        
                        # 并发限制：如果正在运行的工作流太多，跳过
                        if len(self.running_workflows) >= self.max_concurrent_workflows:
                            trade_logger.debug(f"并发限制，跳过 | {symbol} | event_id={event_id} | 运行中={len(self.running_workflows)}")
                            await self.redis.xack(self.l1_stream, self.group, entry_id)
                            continue
                        
                        # 记录接收到的事件
                        trade_logger.info(f"收到L1事件 | {symbol} | direction={ev.get('direction')} | score={ev.get('total_score')} | priority={ev.get('result_priority', ev.get('priority', 'low'))}")
                        self._log_trade_event("L1_EVENT_RECEIVED", symbol, {
                            "entry_id": entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id),
                            "direction": ev.get("direction"),
                            "market_state": ev.get("market_state"),
                            "total_score": ev.get("total_score"),
                            "priority": ev.get("result_priority", ev.get("priority", "low"))
                        })
                        
                        # 构建 info 对象（兼容 SignalValidationWorkflow）
                        info = {
                            "route": "indicators",  # 标记为 indicators 类型
                            "exchange": exchange,
                            "symbol": symbol,
                            "final_priority": ev.get("result_priority", ev.get("priority", "low")),
                            "event_id": event_id,
                            "event_type": "l1_aggregated",
                            "timestamp": ev.get("timestamp", ev.get("ts", "")),
                            
                            # L1 事件数据
                            "market_state": ev.get("market_state", ""),
                            "direction": ev.get("direction", ""),
                            "confidence": ev.get("confidence", "medium"),
                            "confidence_numeric": float(ev.get("total_score", 0)),
                            "priority_weight": 0,
                            "l1_total_score": float(ev.get("total_score", 0)),
                            "tf_hint": ev.get("tf_hint", []),
                            "analysis_context": {
                                "l1_total_score": float(ev.get("total_score", 0)),
                                "tf_hint": ev.get("tf_hint", [])
                            },
                            
                            # 元数据
                            "meta": {
                                "origin_source_hint": "indicators",
                                "source_event_id": event_id
                            },
                            "trade_details": {}
                        }
                        
                        # 记录开始处理
                        trade_logger.info(f"触发工作流 | {symbol} | event_id={event_id} | direction={info.get('direction')} | score={info.get('l1_total_score')}")
                        self._log_trade_event("TRADE_WORKFLOW_START", symbol, {
                            "event_id": event_id,
                            "direction": info.get("direction"),
                            "total_score": info.get("l1_total_score")
                        })
                        
                        # 获取当前价格
                        mark_price = await get_mark_price_from_redis(exchange, symbol)
                        if mark_price:
                            info["mark_price"] = mark_price
                        
                        # 异步入库事件
                        asyncio.create_task(self.event_recorder.save_event(info, mark_price))
                        
                        # 触发交易决策工作流
                        try:
                            # 添加到运行中集合
                            self.running_workflows.add(event_id)
                            
                            wf = SignalValidationWorkflow()
                            # 异步启动工作流（不等待完成）
                            workflow_task = asyncio.create_task(wf.arun(info))
                            
                            # 等待工作流完成并记录结果（完成后从集合中移除）
                            asyncio.create_task(self._wait_and_log_workflow(symbol, event_id, workflow_task))
                        except Exception as e:
                            # 出错时也要从集合中移除
                            self.running_workflows.discard(event_id)
                            trade_logger.error(f"工作流启动失败 | {symbol} | event_id={event_id} | error={e}")
                            self._log_trade_event("WORKFLOW_ERROR", symbol, {
                                "event_id": event_id,
                                "error": str(e)
                            })
                        
                        # 确认消息已处理
                        await self.redis.xack(self.l1_stream, self.group, entry_id)
                        
            except Exception as e:
                trade_logger.error(f"处理事件时出错: {e}")
                await asyncio.sleep(1)

    async def _wait_and_log_workflow(self, symbol: str, event_id: str, workflow_task):
        """等待工作流完成并记录结果"""
        try:
            result = await workflow_task
            
            # 处理 WorkflowRunOutput 对象
            if hasattr(result, 'content'):
                # 如果 result 是 WorkflowRunOutput，提取 content
                result_content = result.content
            elif hasattr(result, '__dict__'):
                # 如果是其他对象，尝试转换为字典
                try:
                    result_content = json.loads(json.dumps(result, default=str))
                except:
                    result_content = str(result)
            else:
                result_content = result
            
            # 解析结果，提取决策信息
            try:
                if isinstance(result_content, str):
                    result_data = json.loads(result_content)
                else:
                    result_data = result_content
                
                trade_decision = result_data.get("trade_decision", {})
                decision = trade_decision.get("decision", "UNKNOWN")
                should_execute = trade_decision.get("should_execute", False)
                
                trade_logger.info(f"工作流完成 | {symbol} | event_id={event_id} | decision={decision} | should_execute={should_execute}")
            except Exception as parse_error:
                trade_logger.debug(f"解析工作流结果失败 | {symbol} | {parse_error}")
            
            # 序列化结果用于存储
            try:
                if isinstance(result_content, str):
                    result_str = result_content
                else:
                    result_str = json.dumps(result_content, ensure_ascii=False, default=str)
            except Exception as serialize_error:
                result_str = str(result_content)
                trade_logger.debug(f"序列化结果失败，使用字符串表示 | {symbol} | {serialize_error}")
            
            self._log_trade_event("TRADE_WORKFLOW_COMPLETE", symbol, {
                "event_id": event_id,
                "result": result_str
            })
        except Exception as e:
            trade_logger.error(f"工作流异常 | {symbol} | event_id={event_id} | error={e}")
            self._log_trade_event("WORKFLOW_EXCEPTION", symbol, {
                "event_id": event_id,
                "error": str(e)
            })
        finally:
            # 无论成功还是失败，都要从运行中集合移除
            self.running_workflows.discard(event_id)


async def _run():
    redis = aioredis.Redis(
        host=settings.redis_host, 
        password=settings.redis_password, 
        port=settings.redis_port,
        db=settings.redis_db, 
        decode_responses=True
    )
    listener = TradeL1Listener(redis)
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _on_sig(*_):
        trade_logger.info("收到停止信号，正在关闭...")
        print("\n[TradeListener] 收到停止信号，正在关闭...")
        stop.set()

    # Windows 不支持 add_signal_handler，需要捕获 NotImplementedError
    is_windows = False
    try:
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except NotImplementedError:
        # Windows 系统不支持，使用 KeyboardInterrupt 处理
        is_windows = True
    task = asyncio.create_task(listener.run(), name="trade_l1_listener")
    
    try:
        while not stop.is_set():
            await asyncio.sleep(0.3)
    except asyncio.CancelledError:
        # Windows 上，KeyboardInterrupt 会导致任务被取消
        if is_windows:
            trade_logger.info("收到停止信号，正在关闭... (KeyboardInterrupt)")
            print("\n[TradeListener] 收到停止信号，正在关闭...")
        raise
    finally:
        try:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            pass
        await redis.aclose()
        trade_logger.info("Trade L1 Listener 已停止")
        print("[TradeListener] 已停止")


def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    # 减少其他 logger 的噪音（将 LLM API 错误降级，这些会被自动重试）
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("agno").setLevel(logging.CRITICAL)
    logging.getLogger("agno.workflow").setLevel(logging.CRITICAL)
    logging.getLogger("agno.agent").setLevel(logging.CRITICAL)
    logging.getLogger("agno.models").setLevel(logging.CRITICAL)
    logging.getLogger("agno.models.openai").setLevel(logging.CRITICAL)  # LLM API 错误会被重试，不需要显示
    
    asyncio.run(_run())


if __name__ == "__main__":
    main()

