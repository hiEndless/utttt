import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from agent_server.utils.db_utils import PostgresDB
from agent_server.tools.get_position import get_position

logger = logging.getLogger(__name__)

class AnalysisVerifier:
    """
    Agent 分析结果验证组件
    负责根据价格走势验证之前的 Agent 分析建议是否准确
    """
    
    def __init__(self, db: PostgresDB, executor: ThreadPoolExecutor):
        """
        初始化验证器
        :param db: 数据库连接实例 (复用 TradeEventRecorder 的连接)
        :param executor: 线程池执行器 (复用 TradeEventRecorder 的线程池)
        """
        self.db = db
        self.executor = executor

    async def verify_previous_analyses(self, current_event_info: Dict[str, Any], current_mark_price: float) -> None:
        """
        验证上一个事件的 Agent 分析结果
        依据：当前价格 vs 上一次分析时的价格
        
        逻辑：
        1. 找到该 symbol 下的所有活跃 trade_id
        2. 对每个 trade_id，查找其未验证的历史事件 (is_verified=False)
        3. 对这些事件的分析结果进行验证
        """
        try:
            exchange = current_event_info.get("exchange", "").lower()
            symbol = current_event_info.get("symbol", "")
            
            # 过滤开平仓事件
            event_type = current_event_info.get("event_type", "").lower()
            if "trade.open" in event_type:
                return

            if not exchange or not symbol or current_mark_price is None:
                return

            # 1. 获取活跃的 trade_ids
            # 复用 recorder 的逻辑，或者直接查询 DB/Redis
            # 这里为了简单直接查询，后续可以考虑传入 trade_ids
            loop = asyncio.get_running_loop()
            trade_ids = await loop.run_in_executor(
                self.executor,
                self._get_active_trade_ids_sync,
                exchange,
                symbol
            )
            
            if not trade_ids:
                return

            # 2. 异步执行验证
            await loop.run_in_executor(
                self.executor,
                self._verify_previous_analyses_sync,
                trade_ids,
                current_mark_price
            )
            
        except Exception as e:
            logger.error(f"验证分析结果失败: {e}", exc_info=True)

    def _get_active_trade_ids_sync(self, exchange: str, symbol: str) -> List[str]:
        """
        获取需要验证的 trade_id 列表 (同步方法)
        
        策略：不依赖 Redis 的活跃状态，而是直接查询数据库中该 Symbol 下
        所有存在“未验证事件”的 Trade。这样即使交易已平仓（Redis已清除），
        只要有遗留的未验证事件，也能被捞出来处理。
        """
        trade_ids = []
        try:
            # 直接联表查询：找到所有在该 exchange/symbol 下，且有未验证分析记录的 trade_id
            # 注意：trade_events 表的外键是 trade_id (对应 trades.trade)
            sql = """
                SELECT DISTINCT te.trade_id
                FROM trade_events te
                JOIN trades t ON te.trade_id = t.trade
                WHERE t.exchange = %s 
                  AND t.symbol = %s
                  AND te.is_verified = FALSE
                  AND EXISTS (SELECT 1 FROM agent_analyses aa WHERE aa.event_id = te.id)
            """
            
            results = self.db.fetch_all(sql, [exchange, symbol])
            
            if results:
                for row in results:
                    # fetch_all 返回的是元组列表或者是字典列表（取决于 db_utils 实现）
                    # 根据之前的代码逻辑，这里似乎可能返回元组或字典
                    tid = row[0] if isinstance(row, tuple) else row.get("trade_id")
                    if tid:
                        trade_ids.append(tid)
            
            return trade_ids
            
        except Exception as e:
            logger.error(f"查询待验证 trade_id 失败: {e}")
            return []

    def _verify_previous_analyses_sync(self, trade_ids: List[str], current_price: float):
        """
        同步执行验证逻辑
        遍历每个 trade_id，查找其未验证的事件进行验证
        """
        for tid in trade_ids:
            try:
                # 1. 获取持仓方向
                sql_trade = "SELECT position_side FROM trades WHERE trade = %s"
                trade_row = self.db.fetch_one(sql_trade, [tid])
                if not trade_row:
                    continue
                
                position_side = trade_row.get("position_side", "").upper() # LONG / SHORT
                if position_side not in ("LONG", "SHORT"):
                    continue

                # 2. 查找该交易下所有未验证且有分析记录的事件
                # 注意：可能存在多个积压的未验证事件，我们一次性处理掉，或者只处理最近的一个
                # 按照用户需求：查找之前没有验证的事件
                # 这里的逻辑是：只要是该 trade_id 下的，且 is_verified=False，且有 agent_analyses 的，都应该验证
                # 但为了性能和逻辑简单，我们通常只验证最近的一个，或者验证所有符合条件的
                # 考虑到价格是实时变化的，验证“很久以前”的事件可能意义不同（那时的价格和现在的价格比较？）
                # 通常是验证“上一个”事件。
                
                # 修正逻辑：查找最近的一个未验证事件
                sql_event = """
                    SELECT te.id, te.mark_price, te.event_at
                    FROM trade_events te
                    WHERE te.trade_id = %s 
                      AND te.is_verified = FALSE
                      AND EXISTS (SELECT 1 FROM agent_analyses aa WHERE aa.event_id = te.id)
                    ORDER BY te.event_at DESC
                    LIMIT 1
                """
                event_row = self.db.fetch_one(sql_event, [tid])
                
                if not event_row:
                    continue
                
                event_pk = event_row.get("id")
                prev_price = event_row.get("mark_price")
                
                # 如果 event 表里没有 mark_price，尝试从 analysis 表里获取
                if prev_price is None:
                    sql_analysis_price = "SELECT mark_price FROM agent_analyses WHERE event_id = %s LIMIT 1"
                    ana_row = self.db.fetch_one(sql_analysis_price, [event_pk])
                    if ana_row:
                        prev_price = ana_row.get("mark_price")
                
                if prev_price is None or float(prev_price) == 0:
                    continue
                
                prev_price = float(prev_price)
                
                # 3. 计算涨跌幅
                pct_change = (current_price - prev_price) / prev_price
                
                # 4. 获取该事件的所有分析记录
                sql_analyses = "SELECT id, suggestion, mark_price FROM agent_analyses WHERE event_id = %s"
                analyses = self.db.fetch_all(sql_analyses, [event_pk])
                
                # 5. 逐个验证
                import time
                verification_time = int(time.time() * 1000)
                
                for ana in analyses:
                    ana_id = ana.get("id")
                    suggestion = ana.get("suggestion")
                    
                    if not suggestion:
                        continue
                        
                    # 判断逻辑
                    is_accurate = self._judge_accuracy(position_side, pct_change, suggestion)
                    
                    # 更新 analysis
                    update_ana_sql = "UPDATE agent_analyses SET is_accurate = %s WHERE id = %s"
                    self.db.execute(update_ana_sql, [is_accurate, ana_id])
                
                # 6. 标记事件为已验证
                update_event_sql = "UPDATE trade_events SET is_verified = TRUE, verification_at = %s WHERE id = %s"
                self.db.execute(update_event_sql, [verification_time, event_pk])
                
                logger.info(f"已验证事件分析: trade_id={tid}, event_pk={event_pk}, change={pct_change:.4%}, side={position_side}")
                
            except Exception as e:
                logger.error(f"验证单个交易失败: trade_id={tid}, {e}")

    def _judge_accuracy(self, position_side: str, pct_change: float, suggestion: str) -> str:
        """
        根据价格变化和建议判断准确性
        """
        # 阈值
        THRESHOLD = 0.005 # 0.5%
        
        suggestion = suggestion.upper()
        
        is_favorable = False
        is_unfavorable = False
        is_sideways = abs(pct_change) < THRESHOLD
        
        if not is_sideways:
            if position_side == "LONG":
                if pct_change > 0: is_favorable = True
                else: is_unfavorable = True
            else: # SHORT
                if pct_change < 0: is_favorable = True
                else: is_unfavorable = True
        
        # 判定
        if is_favorable:
            if suggestion in ("ADD_POSITION", "HOLD"):
                return "ACCURATE"
            elif suggestion == "DEFENSIVE":
                return "NEUTRAL"
            elif suggestion in ("REDUCE", "EXIT"):
                return "INACCURATE"
                
        elif is_unfavorable:
            if suggestion in ("REDUCE", "EXIT", "DEFENSIVE"):
                return "ACCURATE"
            elif suggestion in ("ADD_POSITION", "HOLD"):
                return "INACCURATE"
                
        else: # is_sideways
            if suggestion in ("HOLD", "DEFENSIVE"):
                return "ACCURATE"
            elif suggestion == "ADD_POSITION":
                return "INACCURATE"
            elif suggestion in ("REDUCE", "EXIT"):
                return "NEUTRAL"
        
        return "NEUTRAL"
