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
            await self.redis.xgroup_create(cfg.l1_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[Final] 启动 输入流={cfg.l1_stream} 输出流={cfg.final_stream} 消费组={group}")
        min_priority = os.getenv("FINAL_MIN_PRIORITY", "low")
        # 当仅消费L1时，不再比较L0，only_upgraded逻辑失效
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.l1_stream: ">"}, count=20, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}
                    account = ev.get("account_id")
                    symbol = ev.get("symbol")
                    try:
                        l1_ts = int(ev.get("timestamp") or "0")
                    except Exception:
                        l1_ts = 0
                    direction = ev.get("direction") or ""
                    market_state = ev.get("market_state") or ""
                    short_bias = (ev.get("short_term_bias") or "false").lower() == "true"
                    mid_bias = (ev.get("mid_term_bias") or "false").lower() == "true"
                    cand = ev.get("result_priority") or "low"
                    # 仅使用L1优先级进行过滤
                    if PRIORITY_WEIGHT.get(cand, 0) < PRIORITY_WEIGHT.get(min_priority, 0):
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        continue
                    # 状态切换才输出
                    state_key = f"final:last_state:{account}:{symbol}"
                    last_state = await self.redis.get(state_key)
                    if last_state and last_state == market_state:
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        continue
                    # 时间锁（方向级）
                    now_s = int(l1_ts or 0)
                    lock_key = f"final:lock:{account}:{symbol}:{direction}"
                    last_lock = await self.redis.get(lock_key)
                    min_interval = 180
                    if mid_bias:
                        min_interval = 900
                    elif short_bias:
                        min_interval = 300
                    try:
                        last_lock_s = int(last_lock) if last_lock else 0
                    except Exception:
                        last_lock_s = 0
                    if last_lock_s and (now_s - last_lock_s) < min_interval:
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        continue
                    final = {
                        "event_id": f"{symbol}.final.{l1_ts}",
                        "account_id": account,
                        "symbol": ev.get("symbol"),
                        "timestamp": ev.get("timestamp"),
                        "stage": "final",
                        "event_type": "market.structure",
                        "final_priority": cand,
                        "l0_priority": "",
                        "source_rule_id": "",
                        "direction": direction or "",
                        "market_state": market_state or "",
                    }
                    final = {k: ("" if v is None else v) for k, v in final.items()}
                    try:
                        await self.redis.xadd(cfg.final_stream, final)
                        await self.redis.set(state_key, market_state or "")
                        await self.redis.set(lock_key, str(now_s))
                        print(f"[Final] 输出 event_id={final.get('event_id')} 账户={account} 最终优先级={cand}")
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        print(f"[Final] 确认 entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[Final] 错误 entry_id={entry_id.decode()} 错误={e}")


if __name__ == "__main__":
    fg = FinalGrader()
    asyncio.run(fg.run())
