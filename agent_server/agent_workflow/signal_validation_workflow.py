import uuid
from typing import Optional
from agno.workflow import Workflow

from agent_server.agent_workflow.components.executors.signal_validation_execution import SignalValidationComponent
from agent_server.agent_workflow.components.executors.position_risk_execution import PositionRiskExecutionComponent
from agent_server.agent_workflow.components.executors.trade_decision_execution import TradeDecisionExecutionComponent


class SignalValidationWorkflow(Workflow):
    """
    信号验证工作流：
    1. 信号验证
    2. 持仓风控执行（上下文构建 + 并发评估 + 结果聚合）
    3. 交易决策执行（综合信号、风控、L1事件、市场结构，做出最终交易决策）
    """

    def __init__(self, run_id: Optional[str] = None, **kwargs):
        self.run_id = run_id or str(uuid.uuid4())

        # Initialize components
        self.comp_signal_validation = SignalValidationComponent()
        self.comp_position_risk = PositionRiskExecutionComponent()
        self.comp_trade_decision = TradeDecisionExecutionComponent()

        super().__init__(
            steps=[
                self.comp_signal_validation.execute,
                self.comp_position_risk.execute,
                self.comp_trade_decision.execute,
            ],
            **kwargs
        )
