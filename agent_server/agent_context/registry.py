# Agent 注册表（元信息）
# agent_context/registry.py
from .contracts import AgentContextContract


AGENT_REGISTRY: dict[str, AgentContextContract] = {
    "force_stats": {
        "agent": "force_stats",
        "role": "liquidation_structure",
        "scope": ["micro", "short"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
            "trend_forecast",
            "strategy_advice",
            "mid_term_confirmation",
        ],
        "allowed_paths": [
            "market_state.micro_term.state",

            "market_state.short_term.direction",
            "market_state.short_term.risk",
            "market_state.short_term.confidence",

            "market_state.mid_term.direction",     # reference-only
            "market_state.long_term.veto",          # constraint-only

            "crowd_state.bias",
            "crowd_state.crowding_level",
            "crowd_state.fragility",
            "crowd_state.consistency",
            "crowd_state.funding_pressure",
        ],
    },

    "kline_expert": {
        "agent": "kline_expert",
        "role": "technical_signal",
        "scope": ["micro", "short", "mid"],
        "uses_crowd_state": False,
        "allows_cross_timeframe_inference": True,
        "forbidden_semantics": [
            "crowd_psychology",
        ],
        "allowed_paths": [
            "market_state.micro_term.state",
            "market_state.short_term.direction",
            "market_state.mid_term.direction",
        ],
    },

    "fusion": {
        "agent": "fusion",
        "role": "fusion_decision",
        "scope": ["cross"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": True,
        "forbidden_semantics": [],
        "allowed_paths": [],  # 特殊：full context
    },

    "signal_validation": {
        "agent": "signal_validation",
        "role": "technical_signal",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
            "trend_forecast",
            "strategy_advice",
            "generate_new_direction",
        ],
        "allowed_paths": [
            "market_state.short_term.direction",
            "market_state.short_term.momentum",
            "market_state.short_term.risk",
            "market_state.short_term.confidence",

            "market_state.mid_term.direction",
            "market_state.mid_term.momentum",
            "market_state.mid_term.confidence",

            "market_state.long_term.direction",
            "market_state.long_term.conflict",
            "market_state.long_term.veto",

            "crowd_state.bias",
            "crowd_state.crowding_level",
            "crowd_state.fragility",
            "crowd_state.funding_pressure",
            "crowd_state.consistency",
        ],
    },

    "position_risk": {
        "agent": "position_risk",
        "role": "risk_management",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
            "trend_forecast",
            "strategy_advice",
            "generate_new_direction",
            "override_signal_direction",
        ],
        "allowed_paths": [
            # Market Structure & Trends
            "market_state.long_term.direction",
            "market_state.long_term.veto",
            "market_state.short_term.structure",
            "market_state.short_term.risk",
            "market_state.micro_term.state",

            # Crowd Context
            "crowd_state.crowding_level",
            "crowd_state.funding_pressure",
            "crowd_state.fragility",
            "crowd_state.bias",
        ],
    },

    "trade_event": {
        "agent": "trade_event",
        "role": "trade_analysis",
        "scope": ["micro", "short"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
            "strategy_advice",
        ],
        "allowed_paths": [
            "market_state.micro_term.state",
            "market_state.short_term.direction",
            "market_state.short_term.risk",
            "market_state.mid_term.direction",
            "crowd_state.bias",
            "crowd_state.crowding_level",
            "crowd_state.funding_pressure",
        ],
    },
}
