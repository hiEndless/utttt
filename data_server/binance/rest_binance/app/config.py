import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None)
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_BD', 1))
    rate_limits_seconds: dict = {
        '1m': 10,
        '5m': 10,
        '15m': 25,
        '30m': 25,
        '1h': 40,
        '2h': 40,
        '4h': 50,
        '6h': 50,
        '12h': 60,
        '1d': 60,
    }
    http_timeout_s: int = 10
    log_level: str = "INFO"
    http_proxy: dict = {"http": "http://127.0.0.1:1088"}
    proxy_mode: bool = True  # 本地调试开启本机VPN代理


settings = Settings()
