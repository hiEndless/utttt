# Agent 注册表（元信息）
# agent_context/registry.py
from .contracts import AgentContextContract


AGENT_REGISTRY: dict[str, AgentContextContract] = {
    "signal_validation": {
        "agent": "signal_validation",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.participant_inference.confidence.score",
            "pre_decision_structure.short_term.participant_positioning.participant_inference.behavior",
            "pre_decision_structure.short_term.participant_positioning.confidence.score",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.micro_liquidity.orderbook_structure",
            "pre_decision_structure.short_term.behavioral_intent",
            "pre_decision_structure.short_term.micro_liquidity.orderbook_snapshot",
            "pre_decision_structure.short_term.micro_liquidity.confidence",
            "pre_decision_structure.short_term.participant_positioning.participant_inference.dominant_group",


            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference.dominant_group",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference.behavior",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference.confidence.score",
            "pre_decision_structure.mid_term.participant_positioning.confidence.score",
            "pre_decision_structure.mid_term.participant_positioning.meta",
            "pre_decision_structure.mid_term.behavioral_intent",

            "pre_decision_structure.long_term.structural_context.crowding_percentile.value",
            "pre_decision_structure.long_term.confidence.score",

        ],
    },

    "decision": {
        "agent": "decision",
        "forbidden_paths": [
            "ts",
            "candidate_horizons",

            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.interpretation_tags",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.participant_positioning.confidence.score",
            "pre_decision_structure.short_term.behavioral_intent.interpretation_tags",
            "pre_decision_structure.short_term.behavioral_intent.confidence.score",
            "pre_decision_structure.short_term.structural_risks.liquidity_vacuum",
            "pre_decision_structure.short_term.micro_liquidity",

            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.confidence.score",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference.confidence.score",
            "pre_decision_structure.mid_term.participant_positioning.meta",
            "pre_decision_structure.mid_term.participant_positioning.interpretation_tags",
            "pre_decision_structure.mid_term.participant_positioning.risk_flags",
            "pre_decision_structure.mid_term.behavioral_intent.interpretation_tags",
            "pre_decision_structure.mid_term.behavioral_intent.confidence.score",
            "pre_decision_structure.mid_term.structural_risks.liquidity_vacuum",

            "pre_decision_structure.long_term.structural_context.crowding_percentile.value",
            "pre_decision_structure.long_term.confidence.score",

        ],
    },

    "position_risk": {
        "agent": "position_risk",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.interpretation_tags",
            "pre_decision_structure.short_term.participant_positioning.participant_inference",
            "pre_decision_structure.short_term.participant_positioning.confidence",
            "pre_decision_structure.short_term.behavioral_intent",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.confidence",
            "pre_decision_structure.short_term.micro_liquidity",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.structural_risks.liquidity_vacuum",

            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.interpretation_tags",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference",
            "pre_decision_structure.mid_term.participant_positioning.confidence",
            "pre_decision_structure.mid_term.behavioral_intent",
            "pre_decision_structure.mid_term.participant_positioning.meta",
            "pre_decision_structure.mid_term.confidence",
            "pre_decision_structure.mid_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.structural_risks.liquidity_vacuum",

            "pre_decision_structure.long_term.confidence",
        ]
    },

    "trade_behavior": {
        "agent": "trade_behavior",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.participant_inference.confidence.score",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.micro_liquidity.orderbook_structure",
            "pre_decision_structure.short_term.behavioral_intent",
            "pre_decision_structure.short_term.micro_liquidity.orderbook_snapshot",
            "pre_decision_structure.short_term.micro_liquidity.confidence",


            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference.confidence.score",
            "pre_decision_structure.mid_term.participant_positioning.meta",
            "pre_decision_structure.mid_term.behavioral_intent",

            "pre_decision_structure.long_term.structural_context.crowding_percentile.value",
            "pre_decision_structure.long_term.confidence.score",

        ],
    },

    "market_structure": {
        "agent": "market_structure",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.micro_liquidity",
            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.risk_flags",
            "pre_decision_structure.mid_term.participant_positioning.meta",
        ],
    },

    "trade_decision": {
        "agent": "trade_decision",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.participant_inference",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.micro_liquidity",
            # 保留 behavioral_intent（taker_bias 买卖方数据）供开仓决策使用

            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.participant_inference",
            "pre_decision_structure.mid_term.participant_positioning.meta",
            "pre_decision_structure.mid_term.participant_positioning.risk_flags",
            # 保留 behavioral_intent（taker_bias 买卖方数据）

            "pre_decision_structure.long_term.structural_context.crowding_percentile.value",
            "pre_decision_structure.long_term.confidence",
        ],
    },

    "human_market_narrator": {
        "agent": "human_market_narrator",
        "forbidden_paths": [
            "pre_decision_structure.short_term.participant_positioning.oi_state",
            "pre_decision_structure.short_term.participant_positioning.oi_delta",
            "pre_decision_structure.short_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.short_term.participant_positioning.coupling",
            "pre_decision_structure.short_term.participant_positioning.risk_flags",
            "pre_decision_structure.short_term.participant_positioning.meta",
            "pre_decision_structure.short_term.micro_liquidity",
            "pre_decision_structure.mid_term.participant_positioning.oi_state",
            "pre_decision_structure.mid_term.participant_positioning.oi_delta",
            "pre_decision_structure.mid_term.participant_positioning.oi_dynamics",
            "pre_decision_structure.mid_term.participant_positioning.coupling",
            "pre_decision_structure.mid_term.participant_positioning.risk_flags",
            "pre_decision_structure.mid_term.participant_positioning.meta",
        ],
    },
}
