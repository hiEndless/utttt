import asyncio
from event_center.pipeline.l0_processor import L0Processor
from event_center.pipeline.l1_aggregator import L1Aggregator
from event_center.pipeline.final_grader import FinalGrader
from alerts_consumer import AlertsConsumer
from force_stats_consumer import ForceStatsConsumer
from event_center.indicators_event_generator import EventGenerator, RedisEventWriter
from event_center.config import cfg
from redis import asyncio as aioredis
import json
import time


class IndicatorsScheduler:
    def __init__(self, redis_url: str = cfg.redis_url, intervals=None):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.intervals = intervals or ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        self.periods = {"1m": 20, "5m": 150, "15m": 300, "30m": 600, "1h": 900, "2h": 1800, "4h": 3600, "1d": 43200}
        self.writer = RedisEventWriter(self.redis)

    async def _discover_symbols(self, interval: str):
        pattern = f"indicators:binance:*:{interval}"
        try:
            cursor = 0
            keys = []
            while True:
                cursor, batch = await self.redis.scan(cursor=cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break
            syms = []
            for k in keys:
                parts = str(k).split(":")
                if len(parts) >= 4:
                    syms.append(parts[2])
            return list(set(syms))
        except Exception:
            return []

    async def _read_klines(self, symbol: str, interval: str):
        key = f"klines:binance:{symbol}:{interval}"
        try:
            val = await self.redis.get(key)
            return json.loads(val) if val else []
        except Exception:
            return []

    async def _run_interval(self, interval: str):
        period = self.periods.get(interval, 60)
        while True:
            syms = await self._discover_symbols(interval)
            if not syms:
                await asyncio.sleep(1)
                continue
            for sym in syms:
                kl = await self._read_klines(sym, interval)
                if not kl:
                    continue
                gen = EventGenerator(sym, kl, interval)
                gen.generate_events()
                await gen.publish(self.writer)
            await asyncio.sleep(period)

    async def run(self):
        tasks = [asyncio.create_task(self._run_interval(iv)) for iv in self.intervals]
        await asyncio.gather(*tasks)


async def main():
    l0 = L0Processor()
    l1 = L1Aggregator()
    fg = FinalGrader()
    ac = AlertsConsumer()
    fsc = ForceStatsConsumer()
    isvc = IndicatorsScheduler()
    tasks = [
        asyncio.create_task(ac.run()),
        asyncio.create_task(fsc.run()),
        asyncio.create_task(isvc.run()),
        asyncio.create_task(l0.run()),
        asyncio.create_task(l1.run()),
        asyncio.create_task(fg.run()),
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
