from tortoise import models, fields


class Trade(models.Model):
    """
    交易主表：记录一次完整的交易生命周期
    """
    id = fields.IntField(pk=True, generated=True)
    trade_id = fields.CharField(max_length=64, unique=True, description="交易ID (UUID)")
    symbol = fields.CharField(max_length=32, description="交易对 (e.g. ETHUSDT)")
    exchange = fields.CharField(max_length=32, description="交易所 (e.g. binance)")
    position_side = fields.CharField(max_length=16, description="方向 (LONG/SHORT)")
    size = fields.DecimalField(max_digits=20, decimal_places=8, description="持仓量 (positionAmt)")

    # 时间信息
    entry_time = fields.DatetimeField(description="开仓时间")
    close_time = fields.DatetimeField(null=True, description="平仓时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="记录创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="记录更新时间")

    # 资金信息
    pnl = fields.DecimalField(max_digits=20, decimal_places=8, default=0, description="已实现盈亏")
    
    # 额外信息 (快照)
    entry_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="开仓均价")
    close_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="平仓均价")
    
    class Meta:
        table = "trades"
        indexes = (("symbol", "close_time"),)


class TradeAction(models.Model):
    """
    交易操作记录表：记录开仓、平仓、加仓、减仓等具体操作
    """
    id = fields.IntField(pk=True, generated=True)
    trade_id = fields.ForeignKeyField('models.Trade', related_name='actions', to_field='trade_id', description="关联的交易")
    action_type = fields.CharField(max_length=32, description="操作类型 (OPEN, CLOSE, INCREASE, DECREASE)")
    
    # 核心数据
    amount = fields.DecimalField(max_digits=20, decimal_places=8, description="变动数量 (positionAmt)")
    price = fields.DecimalField(max_digits=20, decimal_places=8, description="成交价格/标记价格 (entryPrice/markPrice)")
    
    # 变动后状态快照
    size = fields.DecimalField(max_digits=20, decimal_places=8, description="变动后总持仓量")
    
    # 时间
    action_at = fields.BigIntField(description="操作时间戳 updateTime")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "trade_actions"
        indexes = (("trade_id", "action_at"),)


class TradeEvent(models.Model):
    """
    交易事件表：记录持仓期间发生的所有关键事件
    例如：价格波动、风控触发、信号更新等
    """
    id = fields.IntField(pk=True, generated=True)
    trade_id = fields.ForeignKeyField('models.Trade', related_name='events', to_field='trade_id', description="关联的交易")
    event_id = fields.CharField(max_length=64, description="事件id")
    event_type = fields.CharField(max_length=32, description="事件类型 (e.g. RISK_CHECK, SIGNAL_UPDATE)")
    event_at = fields.BigIntField(description="事件发生时间戳 (ms)")

    direction = fields.CharField(max_length=16, description="方向 (bullish/bearish/neutral)")
    mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="事件发生时的价格")
    
    # 原始输入快照 (JSON)
    market_context = fields.JSONField(description="市场背景快照 (Trend, Volatility...)")
    event_data = fields.JSONField(description="事件原始数据 (analysis_context)")
    indicators_snapshot = fields.JSONField(null=True, description="关键技术指标快照 (EMA, MACD, RSI...)")
    
    # 验证与总结
    is_verified = fields.BooleanField(default=False, description="是否已验证准确性")
    verification_at = fields.BigIntField(null=True, description="验证时间戳")
    post_summary = fields.TextField(null=True, description="事后总结 (包含准确性复盘)")

    class Meta:
        table = "trade_events"
        indexes = (("trade_id", "event_at"),)


class AgentAnalysis(models.Model):
    """
    Agent 分析记录表：记录每个 Agent 对特定事件的分析结果

    以持多单(LONG)为例的判断逻辑(SHORT同理反之)：
    
    1. 价格上涨(有利方向)：
       - ADD_POSITION: 正确。乘胜追击。
       - HOLD: 正确。坐享其成。
       - DEFENSIVE: 半对半错(或偏向错误)。涨幅猛则踏空；涨幅弱则合理。总体偏保守。
       - REDUCE/EXIT: 错误。卖飞。
    
    2. 价格下跌(不利方向)：
       - ADD_POSITION: 错误。逆势加仓。
       - HOLD: 错误。死扛亏损。
       - DEFENSIVE: 正确。预警风险，可能避免更大损失。
       - REDUCE/EXIT: 正确。及时止损。
    
    3. 价格震荡(幅度<0.5%)：
       - ADD_POSITION: 中性/错误。容易磨损成本。
       - HOLD: 正确。多看少动。
       - DEFENSIVE: 正确。变盘前兆保持警惕。
       - REDUCE/EXIT: 中性。反应过度但规避了不确定性。
    """
    id = fields.IntField(pk=True, generated=True)
    event = fields.ForeignKeyField('models.TradeEvent', related_name='analyses', description="关联的事件")
    agent_name = fields.CharField(max_length=32, description="Agent 名称 (e.g. signal_validation, position_risk)")
    model_version = fields.CharField(max_length=64, null=True, description="模型版本 (e.g. gpt-4-turbo, llama-3-70b)")

    # 核心产出
    verdict = fields.CharField(null=True, max_length=32, description="结论 (VALID, INVALID, HOLD, REDUCE...)")
    confidence = fields.FloatField(null=True, description="置信度 (0-1)")
    
    # 风控专用字段
    suggestion = fields.CharField(max_length=32, null=True, description="持仓建议 (ADD_POSITION, HOLD, DEFENSIVE, REDUCE, EXIT)")
    mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="分析时的标记价格")
    is_accurate = fields.CharField(
        max_length=16, 
        null=True, 
        description="建议准确性 (ACCURATE: 正确预判行情, INACCURATE: 误判/卖飞/死扛, NEUTRAL: 震荡期防守/无功无过)"
    )

    # 详细内容
    reasoning = fields.JSONField(description="分析理由 (List or Dict)")
    full_output = fields.JSONField(description="完整输出 (Raw JSON)")

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "agent_analyses"



