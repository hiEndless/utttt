import asyncio
import json
import os
from redis import asyncio as aioredis

from event_center.config import cfg


PRIORITY_WEIGHT = {
    "low": 10,
    "medium": 50,
    "high": 80,
    "critical": 100,
}


def pick_higher(p1, p2):
    w1 = PRIORITY_WEIGHT.get(p1, 0)
    w2 = PRIORITY_WEIGHT.get(p2, 0)
    return p1 if w1 >= w2 else p2


class FinalGrader:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)

    async def run(self):
        group = "final_group"
        consumer = "final_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.l0_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[Final] started in={cfg.l0_stream} ref_l1={cfg.l1_stream} out={cfg.final_stream} group={group}")
        min_priority = os.getenv("FINAL_MIN_PRIORITY", "low")
        only_upgraded = os.getenv("FINAL_ONLY_UPGRADED", "false").lower() == "true"
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.l0_stream: ">"}, count=20, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}
                    l0_priority = ev.get("priority", "low")
                    account = ev.get("account_id")
                    symbol = ev.get("symbol")
                    try:
                        l0_ts_ms = int(ev.get("timestamp") or "0")
                    except Exception:
                        l0_ts_ms = 0
                    l0_ts_s = int(l0_ts_ms / 1000) if l0_ts_ms else 0
                    l1_entries = await self.redis.xrevrange(cfg.l1_stream, max="+", min="-", count=50)
                    best = l0_priority
                    best_rule_id = ""
                    for sid, f in l1_entries:
                        f2 = {k.decode(): v.decode() for k, v in f.items()}
                        if f2.get("account_id") == account and f2.get("symbol") == symbol:
                            try:
                                l1_ts = int(f2.get("timestamp") or "0")
                            except Exception:
                                l1_ts = 0
                            if l0_ts_s == 0 or l1_ts == 0 or abs(l1_ts - l0_ts_s) <= 900:
                                cand = f2.get("result_priority", "low")
                                prev = best
                                best = pick_higher(best, cand)
                                if best != prev:
                                    best_rule_id = f2.get("rule_id", "")
                    if only_upgraded and PRIORITY_WEIGHT.get(best, 0) <= PRIORITY_WEIGHT.get(l0_priority, 0):
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        continue
                    if PRIORITY_WEIGHT.get(best, 0) < PRIORITY_WEIGHT.get(min_priority, 0):
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        continue
                    final = {
                        "event_id": ev.get("event_id"),
                        "account_id": account,
                        "symbol": ev.get("symbol"),
                        "timestamp": ev.get("timestamp"),
                        "stage": "final",
                        "final_priority": best,
                        "l0_priority": l0_priority,
                        "source_rule_id": best_rule_id,
                    }
                    final = {k: ("" if v is None else v) for k, v in final.items()}
                    try:
                        await self.redis.xadd(cfg.final_stream, final)
                        print(f"[Final] out event_id={final.get('event_id')} account={account} final={best} l0={l0_priority}")
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        print(f"[Final] ack entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[Final] error entry_id={entry_id.decode()} err={e}")


if __name__ == "__main__":
    fg = FinalGrader()
    asyncio.run(fg.run())
