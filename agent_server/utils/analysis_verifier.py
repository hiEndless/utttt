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

    # 需要验证方向性决策的 Agent 列表
    TARGET_AGENTS = ("position_risk",)
    
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
        
        策略：直接根据 is_verified + exchange + symbol 查找
        利用新增的 redundancy fields 进行高效查询
        """
        trade_ids = []
        try:
            # 直接查询 trade_events 表中符合条件的 trade_id
            sql = """
                SELECT DISTINCT trade_id
                FROM trade_events
                WHERE exchange = %s 
                  AND symbol = %s
                  AND is_verified = FALSE
                  AND EXISTS (SELECT 1 FROM agent_analyses aa WHERE aa.event_id = trade_events.id)
            """
            
            results = self.db.fetch_all(sql, [exchange, symbol])
            
            if results:
                for row in results:
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

                # 2. 查找该交易下所有未验证且有目标 Agent 分析记录的事件
                # 不再限制 LIMIT 1，而是获取所有待验证事件
                # 只有当事件包含指定 agent (如 position_risk) 的分析时才需要验证
                
                placeholders = ','.join(['%s'] * len(self.TARGET_AGENTS))
                
                sql_events = f"""
                    SELECT te.id, te.mark_price, te.event_at
                    FROM trade_events te
                    WHERE te.trade_id = %s 
                      AND te.is_verified = FALSE
                      AND EXISTS (
                          SELECT 1 FROM agent_analyses aa 
                          WHERE aa.event_id = te.id 
                          AND aa.agent_name IN ({placeholders})
                      )
                    ORDER BY te.event_at ASC
                """
                
                params = [tid] + list(self.TARGET_AGENTS)
                event_rows = self.db.fetch_all(sql_events, params)
                
                if not event_rows:
                    continue
                
                verification_time = int(time.time() * 1000)

                for event_row in event_rows:
                    event_pk = event_row.get("id")
                    # 使用 tuple index 访问如果 fetch_all 返回的是元组
                    if event_pk is None and isinstance(event_row, tuple):
                         event_pk = event_row[0]
                         
                    prev_price = event_row.get("mark_price")
                    if prev_price is None and isinstance(event_row, tuple):
                        prev_price = event_row[1]

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
                    
                    # 4. 获取该事件的所有分析记录（仅限目标 agent）
                    sql_analyses = f"""
                        SELECT id, suggestion, mark_price, agent_name 
                        FROM agent_analyses 
                        WHERE event_id = %s AND agent_name IN ({placeholders})
                    """
                    ana_params = [event_pk] + list(self.TARGET_AGENTS)
                    analyses = self.db.fetch_all(sql_analyses, ana_params)
                    
                    # 5. 逐个验证
                    has_verification = False
                    for ana in analyses:
                        ana_id = ana.get("id") or (ana[0] if isinstance(ana, tuple) else None)
                        suggestion = ana.get("suggestion") or (ana[1] if isinstance(ana, tuple) else None)
                        
                        if not suggestion:
                            continue
                            
                        # 判断逻辑
                        is_accurate = self._judge_accuracy(position_side, pct_change, suggestion)
                        
                        # 更新 analysis
                        update_ana_sql = "UPDATE agent_analyses SET is_accurate = %s WHERE id = %s"
                        self.db.execute(update_ana_sql, [is_accurate, ana_id])
                        has_verification = True
                    
                    # 6. 标记事件为已验证 (只有当确实进行了验证操作后)
                    if has_verification:
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
