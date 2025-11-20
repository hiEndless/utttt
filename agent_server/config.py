from typing import Dict, List

EVENT_TEAM_MAP: Dict[str, Dict[str, str]] = {
    "market_spike": {
        "low": "default",
        "medium": "delphi",
        "high": "debate",
    },
    "news_break": {
        "low": "default",
        "medium": "n_variant",
        "high": "debate",
    },
}

TEAM_TEMPLATES: Dict[str, List[str]] = {
    "default": ["technical", "risk"],
    "delphi": ["technical", "news", "risk"],
    "debate": ["technical", "news", "risk", "portfolio"],
    "n_variant": ["technical", "news", "risk"],
}

SCORING_WEIGHTS: Dict[str, float] = {
    "technical": 0.35,
    "news": 0.25,
    "risk": 0.25,
    "portfolio": 0.15,
}