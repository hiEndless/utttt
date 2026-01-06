from data_server.binance.ws_binance.utils.db_utils import PostgresDB
import datetime

class TradeRecorder:
    def __init__(self):
        self.db = PostgresDB()

    def _to_datetime(self, ts):
        if not ts:
            return datetime.datetime.now()
        try:
            return datetime.datetime.fromtimestamp(int(ts) / 1000.0)
        except Exception:
            return datetime.datetime.now()

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

            # 插入 Trade 表
            sql_trade = """
                INSERT INTO trades (trade, symbol, exchange, position_side, size, max_size, entry_time, created_at, updated_at, pnl, entry_price)
                VALUES (%s, %s, 'binance', %s, %s, %s, %s, NOW(), NOW(), 0, %s)
                ON CONFLICT (trade) DO NOTHING
            """
            self.db.execute(sql_trade, (trade_id, symbol, position_side, size, size, entry_time, entry_price))

            # 插入 TradeAction 表 (OPEN)
            sql_action = """
                INSERT INTO trade_actions (trade_id, action_type, amount, price, size, action_at, created_at)
                VALUES (%s, 'OPEN', %s, %s, %s, %s, NOW())
            """
            self.db.execute(sql_action, (trade_id, size, entry_price, size, update_time))
            print(f"数据库记录新增交易: {trade_id}")
        except Exception as e:
            print(f"保存新开仓记录失败: {e}")

    def close_trade(self, item, current_time_ms):
        """保存平仓记录"""
        try:
            trade_id = item.get('trade_id')
            close_price = item.get('markPrice', 0)
            close_time = self._to_datetime(current_time_ms)
            
            # 更新 Trade 表 (要靠rest api去更新准确的)
            # 平仓时，增加 closed_size，并将 size 置为 0
            sql_trade = """
                UPDATE trades 
                SET close_time = %s, close_price = %s, updated_at = NOW(), size = 0, closed_size = closed_size + %s
                WHERE trade = %s
            """
            # 平仓数量是负的当前持仓量
            amount = float(item.get('positionAmt', 0)) # amount for closed_size should be positive magnitude
            self.db.execute(sql_trade, (close_time, close_price, amount, trade_id))

            # 插入 TradeAction 表 (CLOSE)
            # 记录动作为负值
            action_amount = -amount
            
            sql_action = """
                INSERT INTO trade_actions (trade_id, action_type, amount, price, size, action_at, created_at)
                VALUES (%s, 'CLOSE', %s, %s, 0, %s, NOW())
            """
            self.db.execute(sql_action, (trade_id, action_amount, close_price, current_time_ms))
            print(f"数据库记录平仓交易: {trade_id}")
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
        except Exception as e:
            print(f"保存交易变更记录失败: {e}")
