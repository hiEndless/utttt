import asyncio
import json
import os
from redis import asyncio as aioredis

from event_center.config import cfg
from event_center.rules import load_rules, match_instant_rule


RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yml")


class L0Processor:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)
        self.rules = load_rules(RULES_PATH)

    async def process_msg(self, entry_id, data: dict):
        event = data
        priority = self.rules.get("default_priority", "low")
        matched_rules = []
        for r in self.rules.get("instant_rules", []):
            if match_instant_rule(event, r):
                priority = r["priority"]
                matched_rules.append(r["id"])
        # support RES v1.0
        payload_s = event.get("payload")
        try:
            payload = json.loads(payload_s) if isinstance(payload_s, str) else (payload_s or {})
        except Exception:
            payload = {"raw": payload_s}
        l0 = {
            "event_id": event.get("event_id"),
            "timestamp": event.get("timestamp"),
            "account_id": event.get("account_id"),
            "symbol": event.get("symbol"),
            "event_class": event.get("event_class") or event.get("class") or "",
            "event_type": event.get("event_type") or event.get("type") or "",
            "event_level": event.get("event_level") or "",
            "payload": json.dumps(payload),
            "priority": priority,
            "matched_rules": json.dumps(matched_rules),
        }
        l0 = {k: ("" if v is None else v) for k, v in l0.items()}
        await self.redis.xadd(cfg.l0_stream, l0)
        print(f"[L0] out event_id={l0.get('event_id')} priority={priority} matched={matched_rules}")

    async def run(self):
        group = "l0_group"
        consumer = "l0_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.raw_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[L0] started raw={cfg.raw_stream} out={cfg.l0_stream} group={group}")
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.raw_stream: ">"}, count=10, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    raw = None
                    if b"data" in fields:
                        try:
                            raw = json.loads(fields[b"data"].decode())
                        except Exception:
                            raw = {}
                    else:
                        raw = {k.decode(): v.decode() for k, v in fields.items()}
                        if "payload" in raw:
                            try:
                                raw["payload"] = json.loads(raw["payload"])
                            except Exception:
                                pass
                    try:
                        print(f"[L0] in entry_id={entry_id.decode()} keys={list(raw.keys())}")
                        await self.process_msg(entry_id.decode(), raw)
                        await self.redis.xack(cfg.raw_stream, group, entry_id)
                        print(f"[L0] ack entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[L0] error entry_id={entry_id.decode()} err={e}")


if __name__ == "__main__":
    lp = L0Processor()
    asyncio.run(lp.run())