import uuid
import asyncio
from typing import Optional
from agno.workflow import Workflow

from agent_server.agent_workflow.components.executors.trade_event_execution import TradeEventExecutionComponent
from agent_server.agent_workflow.components.executors.decision_execution import DecisionExecutionComponent
from agent_server.agent_workflow.components.executors.risk_state_aggregation import RiskStateAggregationComponent
from agent_server.agent_workflow.components.executors.market_structure_execution import MarketStructureExecutionComponent
from agent_server.agent_workflow.components.executors.position_risk_execution import PositionRiskExecutionComponent


class TradeEventWorkflow(Workflow):
    """
    交易事件工作流：
    1. 交易事件分析（trade_behavior）
    2. 决策层（DecisionExecutionComponent：自动兼容 trade / signal 上游输出）
    3. 持仓风控执行（上下文构建 + 并发评估 + 结果聚合）
    4. 风险状态聚合（写入 execution_state / 刷新 global overlay）
    5. 市场结构分析（系统认知与复盘；非关键路径）
    """

    def __init__(self, run_id: Optional[str] = None, **kwargs):
        self.run_id = run_id or str(uuid.uuid4())

        # Initialize components
        self.comp_trade_event = TradeEventExecutionComponent()
        self.comp_decision = DecisionExecutionComponent()
        self.comp_position_risk = PositionRiskExecutionComponent()
        self.comp_risk_state_aggregation = RiskStateAggregationComponent()
        self.comp_market_structure = MarketStructureExecutionComponent()

        super().__init__(
            steps=[
                self.comp_trade_event.execute,
                self.comp_decision.execute,
                self.comp_position_risk.execute,
                self.comp_risk_state_aggregation.execute,
                self.comp_market_structure.execute,
            ],
            **kwargs
        )


if __name__ == "__main__":
    final_signal = {'route': 'trade', 'exchange': 'binance', 'symbol': 'ETHUSDT', 'final_priority': 'low',
                    'event_id': 'binance.ETHUSDT.trade.open.1768803852754', 'event_type': 'trade.open',
                    'timestamp': '1768803852754', 'market_state': None, 'direction': None, 'confidence': None,
                    'confidence_numeric': None, 'priority_weight': None, 'l1_total_score': None, 'tf_hint': None,
                    'analysis_context': {}, 'meta': {'source_event_id': 'binance.ETHUSDT.trade.open.1768803852754',
                                                     'origin_source_hint': 'trade', 'is_short_term': False},
                    'trade_details': {'trade_id': 'e95cbad77cde4d8e80d405d1ff9a6f5f', 'position_side': 'SHORT',
                                      'current_size': '-0.007', 'entry_price': '3193.0', 'mark_price': '3193.00000000',
                                      'pnl_ratio': '0.0', 'action': 'OPEN', 'change_amount': '-0.007'}}

    workflow = TradeEventWorkflow()
    asyncio.run(workflow.arun(final_signal))
