import json
import time
import os
from data_server.binance.ws_binance.utils.reids_connect import RedisClient

class TradeEventPublisher:
    """
    负责将交易变更事件（开仓、平仓、加仓、减仓）推送到 Redis Stream (final_events)。
    该 Stream 与 event_center 的 final_grader 输出共用一个通道，
    供下游（Agent、Dashboard、Notify）统一订阅。
    """

    FINAL_STREAM_KEY = "final_events"

    def __init__(self, exchange: str = "binance"):
        # 复用已有的 RedisClient (基于 sync redis)
        self.redis_client = RedisClient()
        self.exchange = exchange.lower()

    def publish_trade_event(self, event_type: str, item: dict, extra_data: dict = None):
        """
        推送交易事件到 Redis Stream
        :param event_type: 事件类型，如 "TRADE_OPEN", "TRADE_CLOSE", "TRADE_INCREASE", "TRADE_DECREASE"
        :param item: 原始交易数据 item (包含 symbol, trade_id, positionAmt 等)
        :param extra_data: 额外补充的数据 (如 change_amount, pnl 等)
        """
        try:
            ts_ms = int(time.time() * 1000)
            
            # 构建标准化的事件结构
            # 参考 FinalGrader 的输出格式，尽量保持字段风格一致，方便下游解析
            
            symbol = item.get('symbol', 'unknown')
            trade_id = item.get('trade_id', 'unknown')
            
            # 根据 exchange 字段动态设置 account_id
            account_id = f"{self.exchange}_account"

            # 交易详情打包
            trade_details = {
                "trade_id": trade_id,
                "position_side": item.get('positionSide', ''),
                "current_size": str(item.get('positionAmt', '0')), # 当前持仓量
                "entry_price": str(item.get('entryPrice', '0')),
                "mark_price": str(item.get('markPrice', '0')),
                "pnl_ratio": str(item.get('pnl_ratio', '0')), # 收益率
            }

            if extra_data:
                # 将额外数据合并到 trade_details
                for k, v in extra_data.items():
                    trade_details[k] = str(v)

            # 核心业务数据
            payload = {
                "event_id": f"{symbol}.trade.{ts_ms}",
                "stage": "execution",          # 区别于 "final" (market analysis)
                "event_type": event_type,      # 具体交易动作
                "account_id": account_id,
                "symbol": symbol,
                "timestamp": str(ts_ms),
                
                # 将详情序列化为 JSON 字符串存储
                "trade_details": json.dumps(trade_details, ensure_ascii=False)
            }

            # 写入 Redis Stream
            # 使用 safe_xadd_sync (虽然 RedisClient 没有暴露，但可以直接调用 conn.xadd)
            # maxlen 设置为 10000 防止无限增长
            self.redis_client.conn.xadd(self.FINAL_STREAM_KEY, payload, maxlen=10000)
            print(f"Trade Event Published: {event_type} {symbol} {trade_id}")

        except Exception as e:
            print(f"Failed to publish trade event: {e}")

    def on_trade_open(self, item):
        self.publish_trade_event("TRADE_OPEN", item, {
            "action": "OPEN",
            "change_amount": item.get('positionAmt', '0')
        })

    def on_trade_close(self, item, amount):
        """
        :param amount: 平仓数量（通常为负值，表示减少）
        """
        self.publish_trade_event("TRADE_CLOSE", item, {
            "action": "CLOSE",
            "change_amount": amount,
            "pnl": item.get('unRealizedProfit', '0') # 这里的 PnL 可能不准，最好是平仓时的 Realized PnL，但 WS 推送可能不带
        })

    def on_trade_increase(self, item, amount):
        self.publish_trade_event("TRADE_INCREASE", item, {
            "action": "INCREASE",
            "change_amount": amount
        })

    def on_trade_decrease(self, item, amount):
        """
        :param amount: 减仓数量（通常为负值）
        """
        self.publish_trade_event("TRADE_DECREASE", item, {
            "action": "DECREASE",
            "change_amount": amount
        })
