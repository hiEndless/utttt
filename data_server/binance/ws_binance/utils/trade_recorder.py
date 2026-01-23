from data_server.binance.ws_binance.utils.db_utils import PostgresDB
from data_server.binance.ws_binance.utils.trade_event_publisher import TradeEventPublisher
from data_server.binance.ws_binance.bn_client.futures_client import BinanceFuturesClient
import datetime

import os

class TradeRecorder:
    def __init__(self, exchange="binance"):
        self.db = PostgresDB()
        self.exchange = exchange
        self.publisher = TradeEventPublisher(exchange=self.exchange)
        
        # 初始化 Binance API Client
        api_key = os.getenv("BINANCE_API_KEY", "gldbpuTRjjrsN2B3MZUYIfAKFAhPNytPIoKForPJ2E79U2aHfcCbI786RmMlAvq0")
        api_secret = os.getenv("BINANCE_API_SECRET", "yKLTQO0mb22PSiGNlT39LO2nVybDAktGIBXX3NfWjflxrR4pm8wady2Dy2LBdg6B")
        self.bn_client = None
        if api_key and api_secret:
            self.bn_client = BinanceFuturesClient(api_key, api_secret)
        
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

    def _sync_last_trade_details(self, trade_id, symbol):
        """调用 REST API 获取最近一笔交易的详细信息并更新数据库"""
        if not self.bn_client:
            return

        try:
            # 获取最近的交易记录
            trades = self.bn_client.get_user_trades(symbol=symbol, limit=10)
            last_trade = self.bn_client.get_last_position(trades)
            
            if last_trade:
                realized_pnl = float(last_trade.get('realizedPnl', 0))
                order_id = str(last_trade.get('orderId', ''))
                action_at = int(last_trade.get('time', 0))
                
                # 更新 trade_actions 表中最新的一条记录
                # 使用子查询找到该 trade_id 下最新的 action
                sql = """
                    UPDATE trade_actions 
                    SET realized_pnl = %s, 
                        order_id = %s, 
                        action_at = %s
                    WHERE id = (
                        SELECT id FROM trade_actions 
                        WHERE trade_id = %s 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    )
                """
                self.db.execute(sql, (realized_pnl, order_id, action_at, trade_id))
                print(f"同步交易详情成功: {trade_id}, pnl={realized_pnl}, order_id={order_id}")
        except Exception as e:
            print(f"同步交易详情失败: {e}")

    def _sync_closed_trade_pnl(self, trade_id, symbol, position_side, entry_time, leverage):
        """
        平仓后同步计算 PnL 和 PnL Ratio
        pnl = gross_pnl
        pnl_ratio = return_pct * leverage
        """
        if not self.bn_client or not entry_time:
            return

        try:
            # 1. Fetch trades (increase limit to cover history)
            trades = self.bn_client.get_user_trades(symbol=symbol, limit=200)
            
            # 2. Calculate closed positions
            closed_positions = self.bn_client.calculate_closed_positions(trades, symbol)
            
            # 3. Match
            target_ts = entry_time.timestamp() * 1000
            matched_cp = None
            
            for cp in closed_positions:
                cp_side = cp.get('side')
                cp_entry_time = cp.get('entry_time')
                
                # 匹配方向且开仓时间接近 (允许 5秒 误差)
                if cp_side == position_side and cp_entry_time and abs(cp_entry_time - target_ts) < 5000:
                    matched_cp = cp
                    break
            
            if matched_cp:
                gross_pnl = matched_cp.get('gross_pnl', 0)
                return_pct = matched_cp.get('return_pct', 0)
                pnl_ratio = return_pct * leverage
                close_time_ms = matched_cp.get('close_time')
                close_time = self._to_datetime(close_time_ms) if close_time_ms else None
                entry_price = matched_cp.get('entry_price', 0)
                close_price = matched_cp.get('close_price', 0)
                
                # 4. Update DB
                sql = """
                    UPDATE trades 
                    SET pnl = %s, 
                        pnl_ratio = %s,
                        close_time = %s,
                        entry_price = %s,
                        close_price = %s,
                        updated_at = NOW()
                    WHERE trade = %s
                """
                self.db.execute(sql, (gross_pnl, pnl_ratio, close_time, entry_price, close_price, trade_id))
                print(f"同步平仓PnL成功: {trade_id}, pnl={gross_pnl}, pnl_ratio={pnl_ratio}, close_time={close_time}, entry_price={entry_price}, close_price={close_price}")
            else:
                print(f"未找到匹配的平仓记录: {trade_id}, symbol={symbol}, side={position_side}")
                
        except Exception as e:
            print(f"同步平仓PnL失败: {e}")

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
                    pnl, pnl_ratio, entry_price
                )
                VALUES (%s, %s, 'binance', %s, %s, %s, %s, %s, NOW(), NOW(), 0, 0, %s)
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
                    action_at, created_at,
                    symbol, exchange, position_side
                )
                VALUES (%s, 'OPEN', %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
            """
            self.db.execute(sql_action, (trade_id, size, entry_price, size, None, None, update_time, symbol, self.exchange, position_side))
            print(f"数据库记录新增交易: {trade_id} (Leverage: {leverage})")
            
            # 推送事件
            self.publisher.on_trade_open(item)
            
            # 同步 REST API 详情
            self._sync_last_trade_details(trade_id, symbol)
            
            # 同步平仓 PnL
            self._sync_closed_trade_pnl(trade_id, symbol, position_side, entry_time, leverage)
        except Exception as e:
            print(f"保存平仓记录失败: {e}")

    def close_trade(self, item, current_time_ms):
        """保存平仓记录"""
        try:
            trade_id = item.get('trade_id')
            close_price = item.get('markPrice', 0)
            close_time = self._to_datetime(current_time_ms)
            
            # 1. 先查询开仓时间，计算持仓时长，同时获取 symbol/position_side
            sql_query_entry = "SELECT entry_time, symbol, position_side FROM trades WHERE trade = %s"
            result = self.db.fetch_one(sql_query_entry, (trade_id,))
            entry_time = result.get('entry_time') if result else None
            symbol = result.get('symbol') if result else item.get('symbol')
            position_side = result.get('position_side') if result else item.get('positionSide')
            
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
                    action_at, created_at,
                    symbol, exchange, position_side
                )
                VALUES (%s, 'CLOSE', %s, %s, 0, %s, %s, %s, NOW(), %s, %s, %s)
            """
            self.db.execute(sql_action, (trade_id, action_amount, close_price, None, None, current_time_ms, symbol, self.exchange, position_side))
            print(f"数据库记录平仓交易: {trade_id}")
            
            # 推送事件
            # 如果 duration < debounce_minutes min，标记为短线交易，下游只验证不分析
            is_short_term = False
            if self.debounce_enabled and duration_minutes < self.debounce_minutes:
                is_short_term = True
                
            self.publisher.on_trade_close(item, action_amount, is_short_term=is_short_term)
            if is_short_term:
                print(f"短线交易平仓 (持仓 {duration_minutes:.2f} 分钟)，已标记 is_short_term=True")

             # 同步 REST API 详情
            self._sync_last_trade_details(trade_id, symbol)
            
            # 同步平仓 PnL
            self._sync_closed_trade_pnl(trade_id, symbol, position_side, entry_time, leverage)
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
            
            symbol = item.get('symbol')
            position_side = item.get('positionSide')

            # 如果 item 中缺失关键信息，尝试从数据库补充
            if not symbol or not position_side:
                info_sql = "SELECT symbol, position_side FROM trades WHERE trade = %s"
                info_res = self.db.fetch_one(info_sql, (trade_id,))
                if info_res:
                    symbol = symbol or info_res.get('symbol')
                    position_side = position_side or info_res.get('position_side')
            
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
                INSERT INTO trade_actions (
                    trade_id, action_type, amount, price, size, action_at, created_at,
                    symbol, exchange, position_side
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
            """
            self.db.execute(sql_action, (trade_id, change_type, amount, price, new_size, update_time, symbol, self.exchange, position_side))
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
            
            # 同步 REST API 详情
            self._sync_last_trade_details(trade_id, symbol)
        except Exception as e:
            print(f"保存交易变更记录失败: {e}")
