"""market_structure: 将 market_raw 证据聚合为按持仓周期的结构化背景。"""

from .build_context import build_horizon_context
from .raw_reader import read_market_raw

__all__ = ["build_horizon_context", "read_market_raw"]
