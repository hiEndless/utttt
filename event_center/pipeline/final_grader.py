import asyncio
import json
import os
from redis import asyncio as aioredis

from event_center.config import cfg


class FinalGrader:
    PRIORITY_WEIGHT = {
        "low": 10,
        "medium": 50,
        "high": 80,
        "critical": 100,
    }

    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)
        self._load_scripts()

    def _load_scripts(self):
        self.check_script = self.redis.register_script("""
            local state_key = KEYS[1]
            local lock_key = KEYS[2]
            local new_state = ARGV[1]
            local new_ts = tonumber(ARGV[2])
            local min_int = tonumber(ARGV[3])

            local last_state = redis.call('get', state_key)
            if last_state and last_state == new_state then
                return 0 -- Blocked by state
            end

            local last_lock = redis.call('get', lock_key)
            if last_lock then
                local last_ts = tonumber(last_lock)
                if last_ts > 0 and (new_ts - last_ts) < min_int then
                    return -1 -- Blocked by time
                end
            end

            -- Valid, update keys
            redis.call('set', state_key, new_state)
            redis.call('set', lock_key, new_ts)
            return 1 -- Allowed
        """)

    async def run(self):
        group = "final_group"
        consumer = "final_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.l1_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[Final] 启动 输入流={cfg.l1_stream} 输出流={cfg.final_stream} 消费组={group}")
        min_priority = os.getenv("FINAL_MIN_PRIORITY", "low")
        
        while True:
            res = await self.redis.xreadgroup(group, consumer, streams={cfg.l1_stream: ">"}, count=20, block=5000)
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    try:
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
                        
                        # 1. Priority Check
                        if self.PRIORITY_WEIGHT.get(cand, 0) < self.PRIORITY_WEIGHT.get(min_priority, 0):
                            await self.redis.xack(cfg.l1_stream, group, entry_id)
                            continue

                        # 2. Determine Interval
                        min_interval = 180
                        if mid_bias:
                            min_interval = 900
                        elif short_bias:
                            min_interval = 300
                            
                        # 3. Atomic State & Time Check
                        state_key = f"final:last_state:{account}:{symbol}"
                        lock_key = f"final:lock:{account}:{symbol}:{direction}"
                        
                        # Use Lua script for atomic check-and-update
                        # State should include direction to allow flipping (e.g. trend:bullish -> trend:bearish)
                        full_state = f"{market_state}:{direction}"
                        
                        result = await self.check_script(
                            keys=[state_key, lock_key],
                            args=[full_state, l1_ts, min_interval]
                        )
                        
                        if result != 1:
                            # Blocked (0=state, -1=time)
                            await self.redis.xack(cfg.l1_stream, group, entry_id)
                            continue

                        # 4. Publish Final Event
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
                        
                        await self.redis.xadd(cfg.final_stream, final)
                        print(f"[Final] 输出 event_id={final.get('event_id')} 账户={account} 最终优先级={cand}")
                        
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        print(f"[Final] 确认 entry_id={entry_id.decode()}")
                        
                    except Exception as e:
                        print(f"[Final] 错误 entry_id={entry_id.decode()} 错误={e}")



if __name__ == "__main__":
    fg = FinalGrader()
    asyncio.run(fg.run())
