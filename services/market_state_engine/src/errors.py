from __future__ import annotations

from typing import List


class FeatureDataUnavailableFromUpstreamError(RuntimeError):
    """Business exception for unavailable critical data from feature_service."""

    def __init__(self, *, exchange: str, symbol: str, degraded_reasons: List[str]) -> None:
        self.exchange = exchange
        self.symbol = symbol
        self.degraded_reasons = [str(x) for x in list(degraded_reasons or []) if x]
        super().__init__("feature_data_unavailable")
