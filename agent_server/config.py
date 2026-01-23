from typing import Dict, List
import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None)
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_DB', 1))
    api_base_url: str = os.environ.get('API_BASE_URL', 'http://localhost:9931/api')
    rate_limits_seconds: dict = {
        '1m': 60,
        '5m': 150,
        '30m': 600,
        '1h': 900,
        '2h': 1800,
        '4h': 3600,
        '1d': 43200,
    }
    http_timeout_s: int = 10
    log_level: str = "INFO"


settings = Settings()


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

# Control optional stages per mode
PIPELINE_OPTIONS: Dict[str, Dict[str, bool]] = {
    "default": {"reflection": False, "fusion": True},
    "delphi": {"reflection": True, "fusion": True},
    "debate": {"reflection": True, "fusion": True},
    "n_variant": {"reflection": True, "fusion": True},
}
