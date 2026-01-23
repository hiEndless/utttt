from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_event import TradeEventExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.agent_context.utils.crowd_interpreter import build_crowd_interpretation
from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.utils.trade_event_recorder import get_recorder
import json
import asyncio
import time


class TradeEventExecutionComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = TradeEventExpert()

    async def execute(self, ctx: StepInput) -> str:
        event_data = ctx.input
        print(f"--- 交易事件分析：{event_data.get('symbol')} ---")

        symbol = event_data.get("symbol", "unknown")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id")

        # 1. 尝试获取并等待有效的市场上下文
        # 无论是开仓还是加仓，如果是实时交易，都应等待后台分析完成，以确保数据一致性
        full_context = await self._wait_for_valid_context(exchange, symbol, event_data)

        # event_type 格式通常为 "trade.open" 或 "trade.close"
        event_type_raw = event_data.get("event_type", "")
        event_action = event_type_raw.split(".")[-1].lower() if event_type_raw else "unknown"

        # 预判逻辑：如果是开仓事件或短线交易，跳过 LLM 分析以节省成本
        is_short_term = event_data.get("is_short_term", False)

        if event_action in ["open", "close"] or is_short_term:
            print(f"  -> 跳过分析: Action={event_action}, ShortTerm={is_short_term}")
            
            # 即使跳过分析，也应该记录市场快照
            if event_id and full_context:
                recorder = get_recorder()
                asyncio.create_task(
                    recorder.update_event_context(
                        event_id=event_id,
                        exchange=exchange,
                        symbol=symbol,
                        market_context=full_context
                    )
                )

            return self._safe_json_dumps({
                "event_data": event_data,
                "output": {"skipped": True, "reason": f"action_{event_action}_shortterm_{is_short_term}"},
                "full_context": full_context,
            })

        # 提取 trade_details 并抽象化
        trade_details = event_data.get("trade_details", {})
        trade_core = abstract_trade_event(trade_details)
        agent_ctx = build_agent_context("trade_event", full_context)
        
        # Inject deterministic crowd interpretation
        position_side = trade_details.get("position_side", "flat")
        interpretation = build_crowd_interpretation(full_context, position_side)
        agent_ctx["crowd_interpretation"] = interpretation

        query = {
            "symbol": symbol,
            "exchange": exchange,
            "event_id": event_id,
            "trade_core": trade_core,
            "context": agent_ctx,
        }

        output_str = await self.expert.run(json.dumps(query, ensure_ascii=False))

        try:
            output_json = json.loads(output_str)
        except:
            output_json = {"raw": output_str}
        
        # 异步更新事件的市场背景快照
        if event_id and full_context:
            recorder = get_recorder()
            asyncio.create_task(
                recorder.update_event_context(
                    event_id=event_id,
                    exchange=exchange,
                    symbol=symbol,
                    market_context=full_context
                )
            )

        return self._safe_json_dumps({
            "event_data": event_data,
            "output": output_json,
            "full_context": full_context,
        })

    async def _wait_for_valid_context(self, exchange: str, symbol: str, event_data: dict) -> dict:
        """
        等待有效的市场背景数据
        策略：
        1. 如果是历史事件（超过5分钟），直接返回当前缓存（不等）。
        2. 如果是实时事件，检查缓存的新鲜度。
        3. 如果缓存失效或为空，轮询等待后台生成（最多等 100秒）。
        """
        # 获取事件发生时间
        event_ts = float(event_data.get("timestamp", 0))
            
        # 如果是秒级时间戳，转毫秒
        if event_ts < 10**12:
            event_ts *= 1000
            
        now_ts = int(time.time() * 1000)
        is_historical = (now_ts - event_ts) > 5 * 60 * 1000  # 5分钟前算历史
        
        full_context = await self._fetch_market_context(exchange, symbol)
        
        if is_historical:
            return full_context

        # 实时事件：检查 Context 有效性
        # 有效定义：Context 生成时间在事件发生时间之后（或非常接近），且内容非空
        # 放宽一点：Context 生成时间在 (Now - 2min) 之后，说明是最近生成的
        
        def _is_valid(ctx):
            if not ctx or not ctx.get("market_state"):
                return False
            ctx_ts = ctx.get("ts", 0)
            # Context 必须足够新鲜（最近 2 分钟内生成的）
            return (now_ts - ctx_ts) < 2 * 60 * 1000

        if _is_valid(full_context):
            return full_context
            
        # 进入等待循环
        print(f"  -> [Wait] 等待最新市场背景: {symbol} (EventDelay={(now_ts-event_ts)/1000:.1f}s)")
        
        max_retries = 30
        interval = 5
        
        for i in range(max_retries):
            await asyncio.sleep(interval)
            full_context = await self._fetch_market_context(exchange, symbol)
            if _is_valid(full_context):
                print(f"  -> [Wait] 成功获取市场背景 (耗时 {(i+1)*interval}s)")
                return full_context
                
        print("  -> [Wait] 等待超时，使用当前可用数据")

        # 特殊处理：如果是 open 事件，且等待超时，说明后台分析可能卡死或延迟过大
        # 此时不应使用旧的 context（可能误导），而是构造一个空的/错误的 context
        event_type_raw = event_data.get("event_type", "")
        event_action = event_type_raw.split(".")[-1].lower() if event_type_raw else "unknown"

        if event_action == "open":
            print("  -> [Timeout] Open 事件超时，构造 Fallback Context")
            return {
                "error": "timed out"
            }

        return full_context
