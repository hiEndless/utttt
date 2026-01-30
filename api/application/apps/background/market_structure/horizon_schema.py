HORIZONS = {
    "short_term": {
        "holding_window": "≤8h",
        "intervals": ["5m", "15m", "30m", "1h"],
        "behavior_windows": ["5s", "15s", "1m", "15m"],
        "weights": {"5m": 0.15, "15m": 0.25, "30m": 0.25, "1h": 0.35},
    },
    "mid_term": {
        "holding_window": "8h–24h",
        "intervals": ["2h", "4h", "6h", "12h"],
        "behavior_windows": ["15m", "1h"],
        "weights": {"2h": 0.15, "4h": 0.25, "6h": 0.25, "12h": 0.35},
    },
    "long_term": {
        "holding_window": "1d+",
        "intervals": ["6h", "12h", "1d"],
        "behavior_windows": ["1h"],
        "weights": {"6h": 0.2, "12h": 0.3, "1d": 0.5},
    },
}