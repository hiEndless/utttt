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

    # Position Risk User Config Defaults
    risk_defaults: dict = {
    }


settings = Settings()

