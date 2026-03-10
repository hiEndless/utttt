from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent_server_new.ports.data.active_events_provider import ActiveEventsProvider


@dataclass(frozen=True)
class RedisActiveEventsConfig:
    redis_url: str = "redis://127.0.0.1:6379/0"
    stream: str = "ec:selected"
    limit_default: int = 20
    scan_factor: int = 5

    @classmethod
    def from_env(cls) -> "RedisActiveEventsConfig":
        redis_url = str(os.getenv("AGENT_ACTIVE_EVENTS_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
        stream = str(os.getenv("AGENT_ACTIVE_EVENTS_STREAM", "ec:selected") or "ec:selected").strip()
        try:
            limit_default = max(1, int(str(os.getenv("AGENT_ACTIVE_EVENTS_LIMIT_DEFAULT", "20") or "20").strip()))
        except Exception:
            limit_default = 20
        try:
            scan_factor = max(1, int(str(os.getenv("AGENT_ACTIVE_EVENTS_SCAN_FACTOR", "5") or "5").strip()))
        except Exception:
            scan_factor = 5
        return cls(
            redis_url=redis_url,
            stream=stream or "ec:selected",
            limit_default=limit_default,
            scan_factor=scan_factor,
        )


class RedisActiveEventsProvider(ActiveEventsProvider):
    """从 Redis stream 读取事件中心输出的 active events。"""

    def __init__(self, *, client: Any, cfg: Optional[RedisActiveEventsConfig] = None) -> None:
        self._client = client
        self._cfg = cfg or RedisActiveEventsConfig()

    @classmethod
    def from_env(cls) -> "RedisActiveEventsProvider":
        cfg = RedisActiveEventsConfig.from_env()
        return cls.from_url(cfg.redis_url, cfg=cfg)

    @classmethod
    def from_url(cls, url: str, *, cfg: Optional[RedisActiveEventsConfig] = None) -> "RedisActiveEventsProvider":
        try:
            import redis  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("未安装 redis 依赖，无法启用 RedisActiveEventsProvider") from exc
        client = redis.Redis.from_url(url, decode_responses=True)
        return cls(client=client, cfg=cfg)

    async def get_active_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._read_events, exchange, symbol)

    def _read_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        target_limit = max(1, int(self._cfg.limit_default))
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

            # 中文注释：统一支持两类资产键，便于兼容历史事件格式。
            asset = str(payload.get("asset") or payload.get("symbol_id") or "").strip().lower()
            if asset:
                has_symbol = symbol_norm in asset
                has_exchange = (exchange_norm in asset) if exchange_norm else True
                if not (has_symbol and has_exchange):
                    continue
            else:
                payload_exchange = str(payload.get("exchange") or "").strip().lower()
                payload_symbol = str(payload.get("symbol") or "").strip().lower()
                if payload_exchange and payload_exchange != exchange_norm:
                    continue
                if payload_symbol and payload_symbol != symbol_norm:
                    continue

            matched.append(payload)
            if len(matched) >= target_limit:
                break
        return matched
