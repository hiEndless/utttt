from __future__ import annotations

from typing import List


class FeatureDataUnavailableFromUpstreamError(RuntimeError):
    """feature_service 返回关键数据不可用时的业务异常。"""

    def __init__(self, *, exchange: str, symbol: str, degraded_reasons: List[str]) -> None:
        self.exchange = exchange
        self.symbol = symbol
        self.degraded_reasons = [str(x) for x in list(degraded_reasons or []) if x]
        super().__init__("feature_data_unavailable")
