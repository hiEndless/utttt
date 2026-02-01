# Agent 注册表（元信息）
# agent_context/registry.py
from .contracts import AgentContextContract


AGENT_REGISTRY: dict[str, AgentContextContract] = {
    "signal_validation": {
        "agent": "signal_validation",
        "role": "technical_signal",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
        ],
    },

    "position_risk": {
        "agent": "position_risk",
        "role": "risk_management",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
        ],
    },

    "trade_event": {
        "agent": "trade_event",
        "role": "trade_analysis",
        "scope": ["micro", "short"],
        "uses_crowd_state": True,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
        ],
    },

    "market_structure": {
        "agent": "market_structure",
        "role": "market_regime",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": False,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
        ],
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

    "human_market_narrator": {
        "agent": "human_market_narrator",
        "role": "market_regime",
        "scope": ["short", "mid", "long"],
        "uses_crowd_state": False,
        "allows_cross_timeframe_inference": False,
        "forbidden_semantics": [
        ],
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
