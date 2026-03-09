from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from redis.asyncio import Redis


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
        ttl_seconds: int = 604800,
        raw_topk: int = 200,
    ) -> None:
        self._redis = redis_client
        self._raw_key_template = raw_key_template
        self._summary_key_template = summary_key_template
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
        summary_key = self._summary_key(exchange, symbol)
        ex, sym = self._normalize(exchange, symbol)

        entry = _safe_dict(payload)
        entry_ts = int(entry.get("ts") or time.time() * 1000)
        entry["ts"] = entry_ts
        await self._redis.lpush(raw_key, json.dumps(entry, ensure_ascii=False))
        await self._redis.ltrim(raw_key, 0, self._raw_topk - 1)
        await self._redis.expire(raw_key, self._ttl_seconds)

        signal = _safe_dict(entry.get("signal"))
        plan = _safe_dict(entry.get("plan"))
        summary = {
            "exchange": ex,
            "symbol": sym,
            "last_decision_ts": entry_ts,
            "last_signal_direction": str(signal.get("direction") or "none"),
            "last_signal_verdict": str(signal.get("verdict") or "unknown"),
            "last_plan_action": str(plan.get("action") or "hold"),
            "last_plan_direction": str(plan.get("direction") or "none"),
        }
        # 这里使用 LLEN 保持 event_count 与实际 raw 长度一致。
        summary["event_count"] = int(await self._redis.llen(raw_key))
        await self._redis.set(summary_key, json.dumps(summary, ensure_ascii=False))
        await self._redis.expire(summary_key, self._ttl_seconds)


def create_redis_client_from_env(redis_url: Optional[str] = None) -> Redis:
    cfg = RedisSymbolMemoryConfig.from_env()
    return Redis.from_url(redis_url or cfg.redis_url, decode_responses=cfg.decode_responses)
