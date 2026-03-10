from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from market_state_engine.ports.selected_event_provider import SelectedEventProvider


@dataclass(frozen=True)
class RedisSelectedEventProviderConfig:
    stream: str = "ec:selected"
    limit_default: int = 20
    scan_factor: int = 5


class RedisSelectedEventProvider(SelectedEventProvider):
    """从 Redis stream 读取 event_center_new 的 selected_event。"""

    def __init__(self, *, client: Any, cfg: Optional[RedisSelectedEventProviderConfig] = None) -> None:
        self._client = client
        self._cfg = cfg or RedisSelectedEventProviderConfig()

    @classmethod
    def from_url(cls, url: str, *, cfg: Optional[RedisSelectedEventProviderConfig] = None) -> "RedisSelectedEventProvider":
        try:
            import redis  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("未安装 redis 依赖，无法启用 RedisSelectedEventProvider") from exc
        client = redis.Redis.from_url(url, decode_responses=True)
        return cls(client=client, cfg=cfg)

    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        # 中文注释：Redis 客户端为同步实现，使用 to_thread 避免阻塞事件循环。
        return await asyncio.to_thread(self._read_selected_events, exchange, symbol, limit)

    def _read_selected_events(self, exchange: str, symbol: str, limit: int) -> List[Dict[str, Any]]:
        target_limit = max(1, int(limit or self._cfg.limit_default))
        scan_count = max(target_limit, target_limit * max(1, int(self._cfg.scan_factor)))
        rows = self._client.xrevrange(self._cfg.stream, "+", "-", count=scan_count)

        exchange_norm = str(exchange or "").strip().lower()
        symbol_norm = str(symbol or "").strip().lower()
        matched: List[Dict[str, Any]] = []

        for _, fields in list(rows or []):
            payload_raw = (fields or {}).get("payload")
            if not isinstance(payload_raw, str) or not payload_raw:
                continue
            try:
                payload = json.loads(payload_raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            asset = str(payload.get("asset") or "").strip().lower()
            if not asset:
                continue
            # 中文注释：asset 形态可能是 "binance:ETHUSDT" 或仅 symbol，使用宽松匹配。
            matches_symbol = symbol_norm in asset
            matches_exchange = (exchange_norm in asset) if exchange_norm else True
            if not (matches_symbol and matches_exchange):
                continue

            matched.append(payload)
            if len(matched) >= target_limit:
                break

        return matched
