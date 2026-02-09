import uuid
import asyncio
from typing import Optional
from agno.workflow import Workflow

from agent_server.agent_workflow.components.executors.signal_validation_execution import SignalValidationComponent
from agent_server.agent_workflow.components.executors.decision_execution import DecisionExecutionComponent
from agent_server.agent_workflow.components.executors.position_risk_execution import PositionRiskExecutionComponent
from agent_server.agent_workflow.components.executors.risk_state_aggregation import RiskStateAggregationComponent


class SignalValidationWorkflow(Workflow):
    """
    信号验证工作流：
    1. 信号验证 (SignalValidationExpert)
    2. 决策层 (DecisionExpert)
    3. 持仓风控执行 (PositionRiskExpert)
    4. 风险状态聚合 (RiskStateAggregationComponent) - 新增：生成 execution_state & global_overlay
    """

    def __init__(self, run_id: Optional[str] = None, **kwargs):
        self.run_id = run_id or str(uuid.uuid4())

        # Initialize components
        self.comp_signal_validation = SignalValidationComponent()
        self.comp_decision = DecisionExecutionComponent()
        self.comp_position_risk = PositionRiskExecutionComponent()
        self.comp_risk_state_aggregation = RiskStateAggregationComponent()

        super().__init__(
            steps=[
                self.comp_signal_validation.execute,
                self.comp_decision.execute,
                self.comp_position_risk.execute,
                self.comp_risk_state_aggregation.execute,
            ],
            **kwargs
        )


if __name__ == "__main__":
    # Test case matching the one provided in the original file
    final_signal = {"route": "mixed", "exchange": "binance", "symbol": "ETHUSDT", "final_priority": "low",
                    "event_id": "ETHUSDT.final.1770290252305", "event_type": "market.structure",
                    "timestamp": "1770290252305", "market_state": "momentum", "direction": "bullish",
                    "confidence": "medium", "confidence_numeric": 0.5, "priority_weight": 10,
                    "l1_total_score": 19.668839999999996, "tf_hint": ["15m", "30m", "1h"],
                    "analysis_context": {"dominant_bucket": "mid", "supporting_buckets": ["mid"],
                                         "tf_hint": ["15m", "30m", "1h"], "l1_total_score": 19.668839999999996,
                                         "bias": {"short": False, "mid": True}, "reason_tags": ["high_structure_score"],
                                         "lock_window_sec": 900, "provenance": {
                            "origin_sources": ["alerts_consumer", "force_stats_consumer", "ind_event_engine"],
                            "origin_source_hint": "mixed"}, "_debug": {
                            "scores": {"bucket_short": "0.0", "bucket_mid": "19.668839999999996", "bucket_long": "0.0"},
                            "dirs": {"short": "neutral", "mid": "bullish", "long": "neutral"},
                            "component_scores": {"momentum": 19.668839999999996}, "indicators": [
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.9599999999999995, "bucket": "mid", "priority": "medium"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.7079999999999997, "bucket": "mid", "priority": "medium"},
                                {"plugin": "depth.liquidity_collapse", "cls": "unknown", "dir": "neutral", "score": 4.0,
                                 "bucket": "short", "priority": "low"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 3.14, "bucket": "mid", "priority": "high"},
                                {"plugin": "force_spike_sell", "cls": "unknown", "dir": "neutral",
                                 "score": 0.3333333333333333, "bucket": "short", "priority": "low"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 2.9672, "bucket": "mid", "priority": "medium"},
                                {"plugin": "single_signal_williams_r", "cls": "momentum", "dir": "bullish",
                                 "score": 3.0644, "bucket": "mid", "priority": "high"}]}},
                    "meta": {"grader_version": "1.2.0",
                             "source_event_id": "binance.binance_public.ETHUSDT.single_signal_williams_r.1770290252305",
                             "ts_unit": "ms", "min_interval_sec": 900, "origin_source_hint": "mixed",
                             "origin_sources": ["alerts_consumer", "force_stats_consumer", "ind_event_engine"]},
                    "trade_details": {}}

    workflow = SignalValidationWorkflow()
    asyncio.run(workflow.arun(final_signal))
