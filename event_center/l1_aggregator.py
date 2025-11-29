import asyncio
import json
import time
from redis import asyncio as aioredis

from event_center.config import cfg
from event_center.rules import load_rules, match_payload_condition


RULES_PATH = "rules.yml"


class L1Aggregator:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)
        self.rules = load_rules(RULES_PATH)
        self.cooldown = {}
        for s in self.rules.get("suppression", []) or []:
            rid = s.get("rule_id")
            cd = s.get("cooldown_seconds")
            if rid and cd:
                self.cooldown[rid] = int(cd)

    def _skey(self, rule_id, group_val):
        return f"agg:{rule_id}:{group_val}"

    async def _insert_and_check(self, rule, event):
        group_by_field = rule.get("group_by")
        group_val = event.get(group_by_field) if group_by_field else "global"
        key = self._skey(rule["id"], group_val)
        now = int(time.time())
        member = f"{now}:{event.get('event_id')}"
        await self.redis.zadd(key, {member: now})
        lookback = int(rule.get("lookback_seconds", 600))
        cutoff = now - lookback
        await self.redis.zremrangebyscore(key, 0, cutoff)
        cnt = await self.redis.zcount(key, cutoff, now)
        cond = rule.get("condition", {})
        if "count" in cond:
            op = cond["count"].get("operator")
            val = int(cond["count"].get("value", 0))
            if op == ">=" and cnt >= val:
                return True, cnt, key, group_val
            if op == ">" and cnt > val:
                return True, cnt, key, group_val
            if op == "<=" and cnt <= val:
                return True, cnt, key, group_val
        return False, cnt, key, group_val

    async def process_l0_event(self, entry_id, data):
        event = data
        for rule in self.rules.get("aggregation_rules", []) or []:
            ef = rule.get("condition", {}).get("event_filter", {})
            if ef.get("type") and ef["type"] != event.get("type"):
                continue
            if not match_payload_condition(event.get("payload", {}), ef.get("payload", {})):
                continue
            hit, cnt, key, group_val = await self._insert_and_check(rule, event)
            if hit:
                lock_key = f"agg_lock:{rule['id']}:{group_val}"
                cooldown = int(self.cooldown.get(rule["id"], 300))
                was_set = await self.redis.setnx(lock_key, str(int(time.time())))
                if was_set:
                    await self.redis.expire(lock_key, cooldown)
                    l1 = {
                        "rule_id": rule["id"],
                        "account_id": event.get("account_id"),
                        "group_val": group_val,
                        "timestamp": int(time.time()),
                        "count": cnt,
                        "result_priority": rule.get("result_priority"),
                    }
                    l1 = {k: ("" if v is None else v) for k, v in l1.items()}
                    await self.redis.xadd(cfg.l1_stream, l1)
                    print(f"[L1] hit rule={rule['id']} group={group_val} count={cnt} priority={l1['result_priority']}")

    async def run(self):
        group = "l1_group"
        consumer = "l1_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.l0_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[L1] started in={cfg.l0_stream} out={cfg.l1_stream} group={group}")
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.l0_stream: ">"}, count=20, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}
                    if "payload" in ev:
                        try:
                            ev["payload"] = json.loads(ev["payload"])
                        except Exception:
                            ev["payload"] = {}
                    try:
                        print(f"[L1] in entry_id={entry_id.decode()} type={ev.get('type')} account={ev.get('account_id')}")
                        await self.process_l0_event(entry_id.decode(), ev)
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        print(f"[L1] ack entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[L1] error entry_id={entry_id.decode()} err={e}")


if __name__ == "__main__":
    la = L1Aggregator()
    asyncio.run(la.run())