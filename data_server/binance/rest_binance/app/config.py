import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None)
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_BD', 1))
    rate_limits_seconds: dict = {
        '1m': 10,
        '5m': 30,
        '30m': 300,
        '1h': 600,
        '2h': 1200,
        '4h': 3600,
        '1d': 3600,
    }
    http_timeout_s: int = 10
    log_level: str = "INFO"


settings = Settings()
