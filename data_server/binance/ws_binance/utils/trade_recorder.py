from data_server.binance.ws_binance.utils.db_utils import PostgresDB
from data_server.binance.ws_binance.utils.trade_event_publisher import TradeEventPublisher
import datetime

import os

class TradeRecorder:
    def __init__(self, exchange="binance"):
        self.db = PostgresDB()
        self.exchange = exchange
        self.publisher = TradeEventPublisher(exchange=self.exchange)
        
        # 防抖配置
        # 默认开启，阈值3分钟
        self.debounce_enabled = os.getenv("TRADE_DEBOUNCE_ENABLED", "true").lower() == "true"
        try:
            self.debounce_minutes = float(os.getenv("TRADE_DEBOUNCE_MINUTES", "3.0"))
        except Exception:
            self.debounce_minutes = 3.0

    def _to_datetime(self, ts):
        if not ts:
            return datetime.datetime.now(datetime.timezone.utc)
        try:
            return datetime.datetime.fromtimestamp(int(ts) / 1000.0, tz=datetime.timezone.utc)
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    def _calculate_leverage(self, item):
        """计算杠杆倍数 = notional / positionInitialMargin"""
        try:
            notional = abs(float(item.get('notional', 0)))
            initial_margin = abs(float(item.get('positionInitialMargin', 0)))
            if initial_margin > 0:
                return int(round(notional / initial_margin))
            return 1  # 默认值
        except Exception:
            return 1

    def save_new_trade(self, item):
        """保存新开仓记录"""
        try:
            trade_id = item.get('trade_id')
            symbol = item.get('symbol')
            position_side = item.get('positionSide')
            size = item.get('positionAmt')
            entry_price = item.get('entryPrice', 0)
            update_time = item.get('updateTime')
            entry_time = self._to_datetime(update_time)
            
            # 计算杠杆
            leverage = self._calculate_leverage(item)

            # 插入 Trade 表
            # 初始化时 pnl, net_pnl, total_commission, pnl_ratio 均为 0
            sql_trade = """
                INSERT INTO trades (
                    trade, symbol, exchange, position_side, leverage, size, max_size, 
                    entry_time, created_at, updated_at, 
                    pnl, net_pnl, total_commission, pnl_ratio, entry_price
                )
                VALUES (%s, %s, 'binance', %s, %s, %s, %s, %s, NOW(), NOW(), 0, 0, 0, 0, %s)
                ON CONFLICT (trade) DO NOTHING
            """
            self.db.execute(sql_trade, (
                trade_id, symbol, position_side, leverage, size, size, entry_time, entry_price
            ))

            # 插入 TradeAction 表 (OPEN)
            # realized_pnl 和 order_id 默认留空，后续通过 REST API 补充
            sql_action = """
                INSERT INTO trade_actions (
                    trade_id, action_type, amount, price, size, 
                    realized_pnl, order_id,
                    action_at, created_at
                )
                VALUES (%s, 'OPEN', %s, %s, %s, %s, %s, %s, NOW())
            """
            self.db.execute(sql_action, (trade_id, size, entry_price, size, None, None, update_time))
            print(f"数据库记录新增交易: {trade_id} (Leverage: {leverage})")
            
            # 推送事件
            self.publisher.on_trade_open(item)
        except Exception as e:
            print(f"保存新开仓记录失败: {e}")

    def close_trade(self, item, current_time_ms):
        """保存平仓记录"""
        try:
            trade_id = item.get('trade_id')
            close_price = item.get('markPrice', 0)
            close_time = self._to_datetime(current_time_ms)
            
            # 1. 先查询开仓时间，计算持仓时长
            sql_query_entry = "SELECT entry_time FROM trades WHERE trade = %s"
            result = self.db.fetch_one(sql_query_entry, (trade_id,))
            entry_time = result.get('entry_time') if result else None
            
            duration_minutes = 0
            if entry_time:
                # entry_time is datetime, close_time is datetime
                duration_seconds = (close_time - entry_time).total_seconds()
                duration_minutes = duration_seconds / 60.0

            # 计算平仓时的杠杆 (防止用户持仓期间调整)
            leverage = self._calculate_leverage(item)

            # 更新 Trade 表
            # 平仓时，增加 closed_size，并将 size 置为 0
            # 注意：pnl, net_pnl, total_commission, pnl_ratio 这里暂时无法准确计算(缺手续费)，
            # 仍需依赖后续的 rest api 修正。这里先更新状态和杠杆。
            sql_trade = """
                UPDATE trades 
                SET close_time = %s, 
                    close_price = %s, 
                    leverage = %s,
                    updated_at = NOW(), 
                    size = 0, 
                    closed_size = closed_size + %s
                WHERE trade = %s
            """
            # 平仓数量是负的当前持仓量
            amount = float(item.get('positionAmt', 0)) # amount for closed_size should be positive magnitude
            self.db.execute(sql_trade, (close_time, close_price, leverage, amount, trade_id))

            # 插入 TradeAction 表 (CLOSE)
            # 记录动作为负值
            action_amount = -amount
            # realized_pnl 和 order_id 默认留空，后续通过 REST API 补充
            
            sql_action = """
                INSERT INTO trade_actions (
                    trade_id, action_type, amount, price, size, 
                    realized_pnl, order_id,
                    action_at, created_at
                )
                VALUES (%s, 'CLOSE', %s, %s, 0, %s, %s, %s, NOW())
            """
            self.db.execute(sql_action, (trade_id, action_amount, close_price, None, None, current_time_ms))
            print(f"数据库记录平仓交易: {trade_id}")
            
            # 推送事件
            # 如果 duration < debounce_minutes min，标记为短线交易，下游只验证不分析
            is_short_term = False
            if self.debounce_enabled and duration_minutes < self.debounce_minutes:
                is_short_term = True
                
            self.publisher.on_trade_close(item, action_amount, is_short_term=is_short_term)
            if is_short_term:
                print(f"短线交易平仓 (持仓 {duration_minutes:.2f} 分钟)，已标记 is_short_term=True")

        except Exception as e:
            print(f"保存平仓记录失败: {e}")

    def update_trade(self, item):
        """保存加减仓记录"""
        try:
            trade_id = item.get('trade_id')
            new_size = float(item.get('new_position_amt', 0))
            price = float(item.get('price', 0))
            update_time = item.get('updateTime')
            change_type = 'INCREASE' if item.get('change') == 'increase' else 'DECREASE'
            
            # 计算变动数量
            old_size = float(item.get('old_position_amt', 0))
            amount = new_size - old_size
            
            # 更新 Trade 表
            if change_type == 'INCREASE':
                # 加仓：更新 size，同时如果新 size 大于 max_size，则更新 max_size
                sql_trade = """
                    UPDATE trades 
                    SET size = %s, 
                        max_size = GREATEST(max_size, %s),
                        updated_at = NOW() 
                    WHERE trade = %s
                """
                self.db.execute(sql_trade, (new_size, new_size, trade_id))
            else:
                # 减仓：更新 size，增加 closed_size
                # 减仓量是负的 amount (因为 amount = new - old < 0)，所以 closed_size 增加 -amount
                decreased_amount = -amount
                sql_trade = """
                    UPDATE trades 
                    SET size = %s, 
                        closed_size = closed_size + %s,
                        updated_at = NOW() 
                    WHERE trade = %s
                """
                self.db.execute(sql_trade, (new_size, decreased_amount, trade_id))

            # 插入 TradeAction 表
            sql_action = """
                INSERT INTO trade_actions (trade_id, action_type, amount, price, size, action_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            self.db.execute(sql_action, (trade_id, change_type, amount, price, new_size, update_time))
            print(f"数据库记录交易变更: {trade_id} {change_type}")
            
            # 推送事件
            # 防抖逻辑：如果距离上一次更新时间 < debounce_minutes 分钟，标记为短线操作
            last_update_time = item.get('lastUpdateTime')
            is_short_term = False
            
            if self.debounce_enabled and last_update_time:
                try:
                    # updateTime 和 lastUpdateTime 都是毫秒级时间戳
                    diff_ms = int(update_time) - int(last_update_time)
                    diff_min = diff_ms / 1000.0 / 60.0
                    if diff_min < self.debounce_minutes:
                        is_short_term = True
                        print(f"加减仓频率过高 ({diff_min:.2f} min)，已标记 is_short_term=True: {trade_id}")
                except Exception as e:
                    print(f"防抖时间计算错误: {e}")

            if change_type == 'INCREASE':
                self.publisher.on_trade_increase(item, amount, is_short_term=is_short_term)
            else:
                self.publisher.on_trade_decrease(item, amount, is_short_term=is_short_term)
        except Exception as e:
            print(f"保存交易变更记录失败: {e}")
