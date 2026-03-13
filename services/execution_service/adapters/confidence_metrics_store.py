from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict

from redis.asyncio import Redis


_DEFAULT_METRICS = {
    "decide_requests_total": 0,
    "confidence_only_requests": 0,
    "decision_confidence_requests": 0,
    "confidence_alias_mismatch_rejections": 0,
}
_PROMPT_PREFIX = "prompt_config_version::"


@dataclass
class InMemoryConfidenceMetricsStore:
    counters: Dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_METRICS))
    prompt_version_counters: Dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    async def record_decide_request(self, *, has_confidence: bool, has_decision_confidence: bool) -> None:
        with self._lock:
            self.counters["decide_requests_total"] = int(self.counters.get("decide_requests_total", 0)) + 1
            if has_confidence and (not has_decision_confidence):
                self.counters["confidence_only_requests"] = int(self.counters.get("confidence_only_requests", 0)) + 1
            if has_decision_confidence:
                self.counters["decision_confidence_requests"] = int(self.counters.get("decision_confidence_requests", 0)) + 1

    async def record_mismatch_rejection(self) -> None:
        with self._lock:
            self.counters["confidence_alias_mismatch_rejections"] = int(
                self.counters.get("confidence_alias_mismatch_rejections", 0)
            ) + 1

    async def record_prompt_config_version(self, *, prompt_config_version: str) -> None:
        version = str(prompt_config_version or "").strip()
        if not version:
            return
        with self._lock:
            self.prompt_version_counters[version] = int(self.prompt_version_counters.get(version, 0)) + 1

    async def snapshot(self) -> Dict[str, int]:
        with self._lock:
            out = dict(_DEFAULT_METRICS)
            out.update({str(k): int(v) for k, v in dict(self.counters or {}).items()})
            return out

    async def snapshot_prompt_config_versions(self) -> Dict[str, int]:
        with self._lock:
            return {str(k): int(v) for k, v in dict(self.prompt_version_counters or {}).items() if str(k).strip()}

    async def reset(self) -> None:
        with self._lock:
            self.counters = dict(_DEFAULT_METRICS)
            self.prompt_version_counters = {}


@dataclass
class RedisConfidenceMetricsStore:
    redis_client: Redis
    key: str = "execution:metrics:confidence_migration"

    async def record_decide_request(self, *, has_confidence: bool, has_decision_confidence: bool) -> None:
        await self.redis_client.hincrby(self.key, "decide_requests_total", 1)
        if has_confidence and (not has_decision_confidence):
            await self.redis_client.hincrby(self.key, "confidence_only_requests", 1)
        if has_decision_confidence:
            await self.redis_client.hincrby(self.key, "decision_confidence_requests", 1)

    async def record_mismatch_rejection(self) -> None:
        await self.redis_client.hincrby(self.key, "confidence_alias_mismatch_rejections", 1)

    async def record_prompt_config_version(self, *, prompt_config_version: str) -> None:
        version = str(prompt_config_version or "").strip()
        if not version:
            return
        await self.redis_client.hincrby(self.key, f"{_PROMPT_PREFIX}{version}", 1)

    async def snapshot(self) -> Dict[str, int]:
        raw = await self.redis_client.hgetall(self.key)
        out = dict(_DEFAULT_METRICS)
        if isinstance(raw, dict):
            for k, v in raw.items():
                name = str(k or "").strip()
                if not name:
                    continue
                if name.startswith(_PROMPT_PREFIX):
                    continue
                try:
                    out[name] = int(v)
                except Exception:
                    continue
        return out

    async def snapshot_prompt_config_versions(self) -> Dict[str, int]:
        raw = await self.redis_client.hgetall(self.key)
        out: Dict[str, int] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                name = str(k or "").strip()
                if not name.startswith(_PROMPT_PREFIX):
                    continue
                version = name[len(_PROMPT_PREFIX) :].strip()
                if not version:
                    continue
                try:
                    out[version] = int(v)
                except Exception:
                    continue
        return out

    async def reset(self) -> None:
        await self.redis_client.delete(self.key)
