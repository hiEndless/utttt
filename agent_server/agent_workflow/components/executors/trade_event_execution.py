from agno.workflow import StepInput
from agent_server.agents.experts.analysis.trade_behavior import TradeBehaviorExpert
from agent_server.agent_context.builder import build_agent_context
from agent_server.agents.experts.analysis.utils.trade_core_data import abstract_trade_event
from agent_server.agent_workflow.components.base import BaseWorkflowComponent
from agent_server.tools.get_position import get_position
from agent_server.agent_context.market_structure.holding_context_from_positions import build_holding_context_from_positions
from agent_server.agent_context.market_structure import output as market_structure_output
from agent_server.agent_context.market_structure.io.background_kline import DEFAULT_INTERVALS
from agent_server.utils.redis_client import get_redis_client
from agent_server.utils.trade_event_recorder import get_recorder
import json
import asyncio
import time


class TradeEventExecutionComponent(BaseWorkflowComponent):
    def __init__(self):
        self.expert = TradeBehaviorExpert()

    def _infer_event_action(self, event_data: dict) -> str:
        # 中文注释：优先从 trade_details.action 推导事件动作（更贴近真实下单语义），再回退 event_type
        trade_details = event_data.get("trade_details") or {}
        td_action = str(trade_details.get("action") or "").strip().upper()
        if td_action:
            return td_action.lower()
        event_type_raw = event_data.get("event_type", "")
        return event_type_raw.split(".")[-1].lower() if event_type_raw else "unknown"

    def _infer_event_type(self, event_data: dict) -> str:
        # 中文注释：事件类型优先由 trade_details.action 生成（trade.open/trade.increase/...），再回退 event_type
        action = self._infer_event_action(event_data)
        if action and action != "unknown":
            return f"trade.{action}"
        return str(event_data.get("event_type") or "unknown")

    async def execute(self, ctx: StepInput) -> str:
        event_data = ctx.input
        print(f"--- 交易事件分析：{event_data.get('symbol')} ---")

        symbol = event_data.get("symbol", "unknown")
        exchange = event_data.get("exchange", "binance")
        event_id = event_data.get("event_id")

        # 1. 尝试获取并等待有效的市场上下文
        # 无论是开仓还是加仓，如果是实时交易，都应等待后台分析完成，以确保数据一致性
        full_context = await self._wait_for_valid_context(exchange, symbol, event_data)

        # 中文注释：事件动作优先从 trade_details.action 获取（例如 OPEN/INCREASE/DECREASE/CLOSE）
        event_action = self._infer_event_action(event_data)

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
                "positions": [],
            })

        # 提取 trade_details 并抽象化
        trade_details = event_data.get("trade_details", {})
        trade_id = trade_details.get("trade_id")
        positions = get_position(exchange, symbol)
        if len(positions) == 2 and trade_id:
            matched_positions = [p for p in positions if str(p.get("trade_id")) == str(trade_id)]
            if matched_positions:
                positions = matched_positions

        holding_context = build_holding_context_from_positions(positions)
        holding_horizon = holding_context.get("horizon") or "short_term"
        trade_details["holding_horizon"] = holding_horizon

        trade_core = await abstract_trade_event(trade_details)
        agent_ctx = build_agent_context("trade_behavior", full_context, horizon=holding_horizon)

        p_side = trade_details.get("position_side")
        p_action = str(trade_details.get("action") or "").upper()
        if p_side == "LONG":
            direction = "bullish" if p_action == "OPEN" else "bearish"
        elif p_side == "SHORT":
            direction = "bearish" if p_action == "OPEN" else "bullish"
        else:
            direction = None

        query = {
            "meta": {
                "symbol": symbol,
                "exchange": exchange,
                "event_id": event_id,
                "event_type": self._infer_event_type(event_data),
                "trade_id": trade_id,
                "direction": direction,
            },
            "trade": trade_core,
            "structure_context": agent_ctx,
            "positions": positions,
        }

        output_str = await self.expert.run(query)

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
            "positions": positions,
        })

    async def _wait_for_valid_context(self, exchange: str, symbol: str, event_data: dict) -> dict:
        """
        等待有效的市场背景数据
        策略：
        1. 如果是历史事件（超过5分钟），直接返回当前缓存（不等）。
        2. 如果不是“新开仓”事件：直接临时生成最新 market_state（避免等待后台异步写入）。
        3. 如果是“新开仓”事件：需要确保 background:{exchange}:{symbol}:{interval} 的全周期背景已刷新，再返回。
        """
        # 中文注释：这里的“新开仓”用 trade_details.action == OPEN 来判定（回退 event_type）
        event_action = self._infer_event_action(event_data)

        # 获取事件发生时间
        event_ts = float(event_data.get("timestamp", 0))
            
        # 如果是秒级时间戳，转毫秒
        if event_ts < 10**12:
            event_ts *= 1000
            
        now_ts = int(time.time() * 1000)
        is_historical = (now_ts - event_ts) > 5 * 60 * 1000  # 5分钟前算历史
        
        if is_historical:
            full_context = await self._fetch_market_context(exchange, symbol)
            return full_context

        # 非开仓事件：直接临时生成最新 market_state（参考 trade_behavior demo）
        if event_action != "open":
            try:
                return await asyncio.wait_for(
                    market_structure_output.build_output(exchange, symbol),
                    timeout=20,
                )
            except Exception as e:
                print(f"  -> [Warn] 临时生成 market_state 失败，回退缓存：{e}")
                return await self._fetch_market_context(exchange, symbol)

        full_context = await self._fetch_market_context(exchange, symbol)

        # 开仓事件：需要等待 market_state 与多周期 background 同步刷新
        # 约束说明：
        # - background 多周期数据是独立写入（Redis key: background:{exchange}:{symbol}:{interval}），这里以 ts(写入毫秒) 判定新鲜度与一致性
        
        def _is_valid(ctx):
            if not ctx or not ctx.get("market_state"):
                return False
            ctx_ts = ctx.get("ts", 0)
            # Context 必须足够新鲜（最近 3 分钟内生成的）
            return (now_ts - ctx_ts) < 3 * 60 * 1000

        async def _read_background_multi_period() -> dict:
            cli = get_redis_client()
            keys = [f"background:{exchange}:{symbol}:{itv}" for itv in DEFAULT_INTERVALS]
            raws = await cli.mget(keys)
            out: dict = {}
            for itv, raw in zip(DEFAULT_INTERVALS, raws):
                if not raw:
                    out[itv] = {}
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    parsed = {}
                out[itv] = parsed if isinstance(parsed, dict) else {}
            return out

        def _is_background_ready(bg_map: dict) -> bool:
            missing = []
            ts_list = []
            for itv in DEFAULT_INTERVALS:
                cell = (bg_map or {}).get(itv) or {}
                ts = int(cell.get("ts") or 0)
                if ts <= 0:
                    missing.append(itv)
                else:
                    ts_list.append(ts)
            if missing:
                return False

            min_ts = min(ts_list)
            max_ts = max(ts_list)

            # 新鲜度：最老的一份也不能太旧（避免混用上一次批次）
            if (now_ts - min_ts) > 5 * 60 * 1000:
                return False

            # 一致性：全周期应近似同批次写入（允许一定抖动/并发差）
            if (max_ts - min_ts) > 120 * 1000:
                return False

            # 相对事件：全周期最新批次应不早于事件发生太久（容忍事件/写入的传输延迟）
            if max_ts < int(event_ts) - 30 * 1000:
                return False

            return True

        bg_map = await _read_background_multi_period()

        if _is_valid(full_context) and _is_background_ready(bg_map):
            return full_context
            
        # 进入等待循环
        print(f"  -> [Wait] 等待开仓全周期背景: {symbol} (EventDelay={(now_ts-event_ts)/1000:.1f}s)")
        
        max_retries = 50
        interval = 2
        
        for i in range(max_retries):
            await asyncio.sleep(interval)
            now_ts = int(time.time() * 1000)
            full_context = await self._fetch_market_context(exchange, symbol)
            bg_map = await _read_background_multi_period()
            if _is_valid(full_context) and _is_background_ready(bg_map):
                print(f"  -> [Wait] 成功获取开仓全周期背景 (耗时 {(i+1)*interval}s)")
                return full_context
                
        print("  -> [Wait] 等待超时，使用当前可用数据")

        print("  -> [Timeout] Open 事件超时，构造 Fallback Context")
        return {"error": "timed out"}
