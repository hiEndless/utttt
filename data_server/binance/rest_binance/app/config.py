import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None),
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_BD', 0))
    api_rate_limit_per_second: int = 20
    rate_limits: dict = {
        'open_interest': 20,
        'funding': 20,
    }
    kline_rate_limits_seconds: dict = {
        '1m': 60,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
    }
    http_timeout_s: int = 10
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
