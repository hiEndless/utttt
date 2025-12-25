import os
import time
from typing import Optional
import redis.asyncio as aioredis
import json
from agent_server.config import settings

PRIORITY_WEIGHT = {"low": 10, "medium": 50, "high": 80, "critical": 100}


def _pass_priority_gate(final_priority: str, min_priority: str) -> bool:
    return PRIORITY_WEIGHT.get(final_priority, 0) >= PRIORITY_WEIGHT.get(min_priority, 0)


class FinalEventsListener:
    def __init__(self, redis: Optional[aioredis.Redis] = None):
        self.redis = redis or aioredis.Redis(
            host=settings.redis_host,
            password=settings.redis_password,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self.final_stream = os.getenv("FINAL_STREAM", "final_events")
        self.min_priority = os.getenv("AGENT_MIN_FINAL_PRIORITY", "medium")
        self.only_upgraded = os.getenv("AGENT_ONLY_UPGRADED", "false").lower() == "true"
        self.cooldown_s = int(os.getenv("AGENT_FINAL_COOLDOWN_S", "600"))
        self.dedup_s = int(os.getenv("AGENT_FINAL_DEDUP_S", "120"))
        self.group = "agent_final_group"
        self.consumer = "agent_final_consumer"

    async def _passes_cooldown(self, symbol: str, tag: str) -> bool:
        key = f"agent_final:cooldown:{symbol}:{tag}"
        try:
            ok = await self.redis.setnx(key, str(int(time.time())))
            if ok:
                await self.redis.expire(key, self.cooldown_s)
            return ok is True
        except Exception:
            return True

    async def _passes_dedup(self, event_id: str) -> bool:
        key = f"agent_final:dedup:{event_id}"
        try:
            ok = await self.redis.setnx(key, "1")
            if ok:
                await self.redis.expire(key, self.dedup_s)
            return ok is True
        except Exception:
            return True

    async def run(self):
        try:
            await self.redis.xgroup_create(self.final_stream, self.group, id="0", mkstream=True)
        except Exception:
            pass
        while True:
            res = await self.redis.xreadgroup(self.group, self.consumer, streams={self.final_stream: ">"}, count=50, block=5000)
            if not res:
                continue
            for _stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k: (v if isinstance(v, str) else str(v)) for k, v in fields.items()}
                    event_id = ev.get("event_id", "")
                    symbol = ev.get("symbol", "")
                    fp = ev.get("final_priority", "low")
                    l0p = ev.get("l0_priority", "low")
                    rid = ev.get("source_rule_id", "")
                    tag = rid or (ev.get("event_type", "") or ev.get("type", "") or "unknown")
                    if not _pass_priority_gate(fp, self.min_priority):
                        await self.redis.xack(self.final_stream, self.group, entry_id)
                        continue
                    if self.only_upgraded and PRIORITY_WEIGHT.get(fp, 0) <= PRIORITY_WEIGHT.get(l0p, 0):
                        await self.redis.xack(self.final_stream, self.group, entry_id)
                        continue
                    if not await self._passes_dedup(event_id):
                        await self.redis.xack(self.final_stream, self.group, entry_id)
                        continue
                    if not await self._passes_cooldown(symbol, tag):
                        await self.redis.xack(self.final_stream, self.group, entry_id)
                        continue
                    # 打印需要分析的事件到终端
                    analysis_event = {
                        "symbol": symbol,
                        "final_priority": fp,
                        "l0_priority": l0p,
                        "source_rule_id": rid,
                        "event_type": ev.get("event_type") or ev.get("type") or "",
                        "timestamp": ev.get("timestamp"),
                        "event_id": event_id,
                    }
                    try:
                        print("[FinalEventsListener] analysis_event", json.dumps(analysis_event, ensure_ascii=False))
                    except Exception:
                        print("[FinalEventsListener] analysis_event", analysis_event)
                    await self.redis.xack(self.final_stream, self.group, entry_id)
