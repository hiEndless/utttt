from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis

from services.agent_server_new.domain.symbol_memory_summary import build_symbol_memory_summary


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _safe_json_load(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


@dataclass(frozen=True)
class RedisSymbolMemoryConfig:
    redis_url: str
    decode_responses: bool = True
    raw_key_template: str = "agent:memory:raw:{exchange}:{symbol}"
    summary_key_template: str = "agent:memory:summary:{exchange}:{symbol}"
    symbol_index_key: str = "agent:memory:symbols:index"
    ttl_seconds: int = 604800
    raw_topk: int = 200

    @classmethod
    def from_env(cls) -> "RedisSymbolMemoryConfig":
        redis_url = str(os.getenv("AGENT_SYMBOL_MEMORY_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
        raw_key_template = str(
            os.getenv("AGENT_SYMBOL_MEMORY_RAW_KEY_TEMPLATE", "agent:memory:raw:{exchange}:{symbol}")
            or "agent:memory:raw:{exchange}:{symbol}"
        ).strip()
        summary_key_template = str(
            os.getenv("AGENT_SYMBOL_MEMORY_SUMMARY_KEY_TEMPLATE", "agent:memory:summary:{exchange}:{symbol}")
            or "agent:memory:summary:{exchange}:{symbol}"
        ).strip()
        symbol_index_key = str(
            os.getenv("AGENT_SYMBOL_MEMORY_INDEX_KEY", "agent:memory:symbols:index")
            or "agent:memory:symbols:index"
        ).strip()
        try:
            ttl_seconds = max(60, int(str(os.getenv("AGENT_SYMBOL_MEMORY_TTL_SECONDS", "604800") or "604800").strip()))
        except Exception:
            ttl_seconds = 604800
        try:
            raw_topk = max(1, int(str(os.getenv("AGENT_SYMBOL_MEMORY_RAW_TOPK", "200") or "200").strip()))
        except Exception:
            raw_topk = 200
        return cls(
            redis_url=redis_url,
            decode_responses=True,
            raw_key_template=raw_key_template,
            summary_key_template=summary_key_template,
            symbol_index_key=symbol_index_key,
            ttl_seconds=ttl_seconds,
            raw_topk=raw_topk,
        )


class RedisSymbolMemoryAdapter:
    """Redis 记忆适配器：同时实现 provider + recorder。"""

    def __init__(
        self,
        *,
        redis_client: Redis,
        raw_key_template: str = "agent:memory:raw:{exchange}:{symbol}",
        summary_key_template: str = "agent:memory:summary:{exchange}:{symbol}",
        symbol_index_key: str = "agent:memory:symbols:index",
        ttl_seconds: int = 604800,
        raw_topk: int = 200,
    ) -> None:
        self._redis = redis_client
        self._raw_key_template = raw_key_template
        self._summary_key_template = summary_key_template
        self._symbol_index_key = str(symbol_index_key or "agent:memory:symbols:index")
        self._ttl_seconds = max(60, int(ttl_seconds))
        self._raw_topk = max(1, int(raw_topk))

    @staticmethod
    def _normalize(exchange: str, symbol: str) -> tuple[str, str]:
        return str(exchange or "").strip().lower(), str(symbol or "").strip().upper()

    def _raw_key(self, exchange: str, symbol: str) -> str:
        ex, sym = self._normalize(exchange, symbol)
        return self._raw_key_template.format(exchange=ex, symbol=sym)

    def _summary_key(self, exchange: str, symbol: str) -> str:
        ex, sym = self._normalize(exchange, symbol)
        return self._summary_key_template.format(exchange=ex, symbol=sym)

    async def get_symbol_memory(self, exchange: str, symbol: str, limit: int = 20) -> Dict[str, Any]:
        raw_key = self._raw_key(exchange, symbol)
        summary_key = self._summary_key(exchange, symbol)
        summary_raw = await self._redis.get(summary_key)
        recent_raw = await self._redis.lrange(raw_key, 0, max(0, int(limit) - 1))
        recent = []
        for item in list(recent_raw or []):
            parsed = _safe_json_load(item)
            if parsed:
                recent.append(parsed)
        recent.reverse()  # 保持时间升序，和 in-memory 实现对齐。
        return {
            "summary": _safe_json_load(summary_raw),
            "recent": recent,
            "ts": int(time.time() * 1000),
        }

    async def record_symbol_memory(self, exchange: str, symbol: str, payload: Dict[str, Any]) -> None:
        raw_key = self._raw_key(exchange, symbol)
        ex, sym = self._normalize(exchange, symbol)
        symbol_id = f"{ex}:{sym}"

        entry = _safe_dict(payload)
        entry_ts = int(entry.get("ts") or time.time() * 1000)
        entry["ts"] = entry_ts
        await self._redis.lpush(raw_key, json.dumps(entry, ensure_ascii=False))
        await self._redis.ltrim(raw_key, 0, self._raw_topk - 1)
        await self._redis.expire(raw_key, self._ttl_seconds)
        await self._redis.sadd(self._symbol_index_key, symbol_id)
        await self.rebuild_symbol_summary(exchange, symbol, window=self._raw_topk)

    async def list_symbols(self, limit: int = 1000) -> List[Dict[str, str]]:
        lim = max(1, int(limit))
        raw_items = list(await self._redis.smembers(self._symbol_index_key) or [])
        out: List[Dict[str, str]] = []
        for item in raw_items:
            key = str(item or "").strip()
            if ":" not in key:
                continue
            exchange, symbol = key.split(":", 1)
            out.append({"exchange": exchange, "symbol": symbol})
            if len(out) >= lim:
                break
        return out

    async def rebuild_symbol_summary(self, exchange: str, symbol: str, *, window: int = 50) -> Dict[str, Any]:
        raw_key = self._raw_key(exchange, symbol)
        summary_key = self._summary_key(exchange, symbol)
        raw_items = await self._redis.lrange(raw_key, 0, max(0, int(window) - 1))
        parsed: List[Dict[str, Any]] = []
        for item in list(raw_items or []):
            payload = _safe_json_load(item)
            if payload:
                parsed.append(payload)
        parsed.reverse()
        summary = build_symbol_memory_summary(
            exchange=exchange,
            symbol=symbol,
            raw_records=parsed,
            window=max(1, int(window)),
        )
        await self._redis.set(summary_key, json.dumps(summary, ensure_ascii=False))
        await self._redis.expire(summary_key, self._ttl_seconds)
        return summary


def create_redis_client_from_env(redis_url: Optional[str] = None) -> Redis:
    cfg = RedisSymbolMemoryConfig.from_env()
    return Redis.from_url(redis_url or cfg.redis_url, decode_responses=cfg.decode_responses)
