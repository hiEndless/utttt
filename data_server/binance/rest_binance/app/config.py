import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None)
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_DB', 1))
    rate_limits_seconds: dict = {
        '1m': 20,
        '5m': 150,
        '15m': 300,
        '30m': 600,
        '1h': 900,
        '2h': 1800,
        '4h': 3600,
        '6h': 7200,
        '12h': 10800,
        '1d': 21600,
    }
    http_timeout_s: int = 10
    log_level: str = "INFO"
    http_proxy: dict = {"http": "http://127.0.0.1:1088"}
    proxy_mode: bool = False  # 本地调试开启本机VPN代理


settings = Settings()
