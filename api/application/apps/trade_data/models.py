from tortoise import models, fields


class Trade(models.Model):
    """
    交易主表：记录一次完整的交易生命周期
    """
    id = fields.IntField(pk=True, generated=True)
    trade = fields.CharField(max_length=64, unique=True, description="交易ID (UUID)")
    symbol = fields.CharField(max_length=32, description="交易对 (e.g. ETHUSDT)")
    exchange = fields.CharField(max_length=32, description="交易所 (e.g. binance)")
    position_side = fields.CharField(max_length=16, description="方向 (LONG/SHORT)")
    leverage = fields.IntField(null=True, description="杠杆倍数")
    size = fields.DecimalField(max_digits=20, decimal_places=8, description="持仓量 (positionAmt)")
    max_size = fields.DecimalField(max_digits=20, decimal_places=8, default=0, description="最大持仓量")
    closed_size = fields.DecimalField(max_digits=20, decimal_places=8, default=0, description="已平仓量")

    # 时间信息
    entry_time = fields.DatetimeField(description="开仓时间")
    close_time = fields.DatetimeField(null=True, description="平仓时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="记录创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="记录更新时间")

    # 资金信息
    pnl = fields.DecimalField(max_digits=20, decimal_places=8, default=0, description="已实现盈亏 (Gross PnL, 包含资金费)")
    pnl_ratio = fields.DecimalField(max_digits=20, decimal_places=8, default=0, description="收益率 (ROI)")
    
    # 额外信息 (快照)
    entry_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="开仓均价")
    close_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="平仓均价")

    summary = fields.JSONField(null=True, description="平仓后交易概要(JSON)")
    # summary中的字段，单独提取存储
    trade_verdict = fields.CharField(
        max_length=32,
        null=True,
        description="交易定性结论 (GOOD_TRADE, BAD_TRADE, GOOD_LOSS, BAD_WIN)"
    )
    
    class Meta:
        table = "trades"
        indexes = (("symbol", "close_time"),)


class TradeAction(models.Model):
    """
    交易操作记录表：记录开仓、平仓、加仓、减仓等具体操作
    """
    id = fields.IntField(pk=True, generated=True)
    trade = fields.ForeignKeyField('models.Trade', related_name='actions', to_field='trade', description="关联的交易")
    action_type = fields.CharField(max_length=32, description="操作类型 (OPEN, CLOSE, INCREASE, DECREASE)")
    
    # 冗余字段方便查询 (用于不关联Trade直接统计收益)
    symbol = fields.CharField(max_length=32, null=True, description="交易对 (e.g. ETHUSDT)")
    exchange = fields.CharField(max_length=32, null=True, description="交易所 (e.g. binance)")
    position_side = fields.CharField(max_length=16, null=True, description="方向 (LONG/SHORT)")

    # 核心数据
    amount = fields.DecimalField(max_digits=20, decimal_places=8, description="变动数量 (positionAmt)")
    price = fields.DecimalField(max_digits=20, decimal_places=8, description="成交价格/标记价格 (entryPrice/markPrice)")
    
    # 变动后状态快照
    size = fields.DecimalField(max_digits=20, decimal_places=8, description="变动后总持仓量")

    # 收益与费用 (基于成交记录重建)
    realized_pnl = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="该笔成交实现的盈亏")
    
    # 交易所原始ID
    order_id = fields.CharField(max_length=64, null=True, description="交易所订单ID")
    
    # 时间
    action_at = fields.BigIntField(description="操作时间戳 updateTime")
    created_at = fields.DatetimeField(auto_now_add=True)
    
    # 人工干预
    follows_system = fields.BooleanField(
        null=True,
        description="是否遵循系统建议"
    )
    # 后续手动补充，用于复盘
    override_reason = fields.CharField(
        max_length=64,
        null=True,
        description="人工干预原因 (fear, conviction, news, discretion...)"
    )

    class Meta:
        table = "trade_actions"
        indexes = (("trade", "action_at"),)


class TradeEvent(models.Model):
    """
    交易事件表：记录持仓期间发生的所有关键事件
    例如：价格波动、风控触发、信号更新等
    """
    id = fields.IntField(pk=True, generated=True)
    trade = fields.ForeignKeyField('models.Trade', related_name='events', to_field='trade', description="关联的交易")
    event_id = fields.CharField(max_length=64, description="事件id")
    event_type = fields.CharField(max_length=32, description="事件类型")
    event_at = fields.BigIntField(description="事件发生时间戳 (ms)")
    
    # 冗余字段方便查询
    symbol = fields.CharField(max_length=32, null=True, description="交易对 (e.g. ETHUSDT)")
    exchange = fields.CharField(max_length=32, null=True, description="交易所 (e.g. binance)")

    direction = fields.CharField(max_length=16, description="方向 (bullish/bearish/neutral)")
    mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="事件发生时的价格")
    
    # 原始输入快照 (JSON)
    market_context = fields.JSONField(null=True, description="市场背景快照 (Trend, Volatility...)")
    market_structure = fields.JSONField(null=True, description="市场快照 (压缩版的背景，供后续回测)")
    event_data = fields.JSONField(description="事件原始数据 (analysis_context)")
    indicators_snapshot = fields.JSONField(null=True, description="关键技术指标快照 (EMA, MACD, RSI...)")
    
    # 验证与总结
    is_verified = fields.BooleanField(default=False, description="是否已验证准确性")
    verification_at = fields.BigIntField(null=True, description="验证时间戳")
    verification_mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="验证时的价格")
    event_importance = fields.IntField(default=0, description="事件重要性 (0-100, 事后评估)")
    event_summary = fields.TextField(null=True, description="事后总结 (包含准确性复盘)")

    class Meta:
        table = "trade_events"
        indexes = (("trade", "event_at"),)


class AgentAnalysis(models.Model):
    """
    Agent 分析记录表：记录每个 Agent 对特定事件的分析结果

    📈 FAVORABLE（行情对持仓有利）
    条件
    LONG 且价格上涨 ≥ 0.5%
    或 SHORT 且价格下跌 ≥ 0.5%

    suggestion	market_accuracy	decision_quality	语义解释
    HOLD	CORRECT	GOOD	扛住正确行情
    SCALE_IN_SMALL	CORRECT	GOOD	在正确方向下风险可控
    REDUCE	WRONG	DEFENSIVE	卖飞，但风险行为合理
    EXIT	WRONG	DEFENSIVE	过早退出，但符合风控

    📉 UNFAVORABLE（行情对持仓不利）
    条件
    LONG 且价格下跌 ≥ 0.5%
    或 SHORT 且价格上涨 ≥ 0.5%

    suggestion(risk_action)	market_accuracy	decision_quality	语义解释
    REDUCE                	CORRECT	        GOOD	            正确止损 / 降风险
    EXIT                	CORRECT	        GOOD	            正确切断风险
    HOLD                	WRONG	        DEFENSIVE	        扛单，风险未扩张
    SCALE_IN_SMALL	        WRONG	        OVERAGGRESSIVE	    在错误方向下扩大风险

    📊 SIDEWAYS（无有效方向）
    条件
    |pct_change| < 0.5%

    suggestion	    market_accuracy	  decision_quality	   语义解释
    HOLD	        NEUTRAL	          GOOD	               符合中性行情
    SCALE_IN_SMALL	NEUTRAL	          GOOD	               风险仍可控
    REDUCE	        NEUTRAL	          DEFENSIVE	           偏保守但合理
    EXIT	        NEUTRAL	          DEFENSIVE	           过度防守但合规
    """
    id = fields.IntField(pk=True, generated=True)
    event = fields.ForeignKeyField('models.TradeEvent', related_name='analyses', description="关联的事件")
    
    # 冗余字段方便查询
    symbol = fields.CharField(max_length=32, null=True, description="交易对 (e.g. ETHUSDT)")
    exchange = fields.CharField(max_length=32, null=True, description="交易所 (e.g. binance)")

    agent_name = fields.CharField(max_length=32, description="Agent 名称 (e.g. signal_validation, position_risk)")
    model_version = fields.CharField(max_length=64, null=True, description="模型版本 (e.g. gpt-4-turbo, llama-3-70b)")

    # 风控专用字段
    risk_action = fields.CharField(max_length=32, null=True, description="持仓风控建议 (hold/reduce/scale_in_small/exit)")
    mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="分析时的标记价格")
    verification_mark_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True, description="验证时的价格")
    
    market_accuracy = fields.CharField(
        max_length=16,
        null=True,
        description="行情判断准确性 (CORRECT, WRONG, NEUTRAL)"
    )
    decision_quality = fields.CharField(
        max_length=16,
        null=True,
        description="决策质量 (GOOD, BAD, DEFENSIVE, OVERAGGRESSIVE)"
    )

    # 详细内容
    reasoning = fields.JSONField(null=True, description="分析理由 (List or Dict)")
    full_output = fields.JSONField(description="完整输出 (Raw JSON)")

    # 风控状态
    execution_state = fields.JSONField(null=True, description="执行状态 (Dict)")
    global_state = fields.JSONField(null=True, description="全局状态 (Dict)")

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "agent_analyses"


