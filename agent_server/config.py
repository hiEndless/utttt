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
        "max_loss_pct": float(os.environ.get('RISK_MAX_LOSS_PCT', -0.3)),
        "max_holding_min": int(os.environ.get('RISK_MAX_HOLDING_MIN', 0)),
        "cooldown_after_invalid_min": int(os.environ.get('RISK_COOLDOWN_MIN', 0)),
        "risk_mode": os.environ.get('RISK_MODE', 'aggressive'),  # normal | conservative | aggressive
        "system_mode": os.environ.get('SYSTEM_MODE', 'advisory'),  # advisory | normal | defensive | recovery
        "allow_reverse": os.environ.get('RISK_ALLOW_REVERSE', 'True').lower() == 'true',
        "allow_add_position": os.environ.get('RISK_ALLOW_ADD_POSITION', 'True').lower() == 'true',
    }

    crowd_thresholds: dict = {
        "extreme_zscore": float(os.environ.get("CROWD_EXTREME_ZSCORE", 2.5)),  # 从2.2提高到2.5，避免主流币正常多头被误判为极端拥挤
        "building_zscore": float(os.environ.get("CROWD_BUILDING_ZSCORE", 2.0)),  # 从1.8提高到2.0，提高拥挤加速判定门槛
        "building_delta": float(os.environ.get("CROWD_BUILDING_DELTA", 0.025)),  # 从0.02提高到0.025，减少小幅波动导致的误判
        "fragility_requires_crowding": os.environ.get("CROWD_FRAGILITY_REQUIRES_CROWDING", "True").lower() == "true",
        "mainstream_bias_adjustment": float(os.environ.get("CROWD_MAINSTREAM_BIAS_ADJUSTMENT", 0.3)),  # 新增：主流币偏向调整系数
    }


settings = Settings()

