"""orderbook: 结构化 orderbook 特征（快照 + 短周期滚动 + 风险旗标）。"""

from .service import build_orderbook_structure
from .output import build_output

__all__ = ["build_orderbook_structure", "build_output"]
