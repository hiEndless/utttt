from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

from api.application.apps.background.kline_indicators import read_multi_period

DEFAULT_INDICATOR_PERIODS: Tuple[str, ...] = (
    "1m",
    "5m",
    "15m",
    "1h",
    "4h",
    "1d",
)


class RedisIndicatorsProvider:
    """Read indicator payloads from data_server output."""

    def __init__(self, periods: Iterable[str] | None = None) -> None:
        self._periods = tuple(periods or DEFAULT_INDICATOR_PERIODS)

    async def get_indicators(self, exchange: str, symbol: str) -> Dict[str, Any]:
        data = await read_multi_period(exchange, symbol, self._periods)
        return dict(data or {})
