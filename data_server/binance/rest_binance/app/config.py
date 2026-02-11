import os


class Settings:
    redis_host: str = os.environ.get('REDIS_HOST', '127.0.0.1')
    redis_password: str = os.environ.get('REDIS_PASSWORD', None)
    redis_port: int = int(os.environ.get('REDIS_PORT', 6379))
    redis_db: int = int(os.environ.get('REDIS_DB', 1))
    # Redis 连接池配置
    redis_max_connections: int = int(
        os.environ.get('REDIS_MAX_CONNECTIONS', 50))  # 连接池最大连接数
    redis_batch_size: int = int(os.environ.get('REDIS_BATCH_SIZE',
                                               100))  # 批量写入大小
    redis_flush_interval: float = float(
        os.environ.get('REDIS_FLUSH_INTERVAL', 0.1))  # 批量写入刷新间隔（秒）
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
