HORIZONS = {
    "short_term": {
        "holding_window": "≤8h",
        "intervals": ["5m", "15m", "30m", "1h", "2h"],
        "weights": {"5m": 0.2, "15m": 0.25, "30m": 0.25, "1h": 0.25, "2h": 0.05},
    },
    "mid_term": {
        "holding_window": "8h–24h",
        "intervals": ["4h", "6h", "12h"],
        "weights": {"4h": 0.25, "6h": 0.35, "12h": 0.4},
    },
    "long_term": {
        "holding_window": "1d+",
        "intervals": ["6h", "12h", "1d"],
        "weights": {"6h": 0.15, "12h": 0.35, "1d": 0.5},
    },
}
