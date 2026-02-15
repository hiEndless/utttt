import asyncio
import os
from event_center.pipeline.l0_processor import L0Processor
from event_center.pipeline.l1_aggregator import L1Aggregator
from event_center.pipeline.final_grader import FinalGrader
from event_center.alerts_consumer import AlertsConsumer
from event_center.force_stats_consumer import ForceStatsConsumer
from event_center.ind_envent_generator import run_loop as ind_event_run_loop
from event_center.config import cfg
from redis import asyncio as aioredis


async def main():
    l0 = L0Processor()
    l1 = L1Aggregator()
    fg = FinalGrader()

    async def _discover_exchanges():
        redis = aioredis.from_url(cfg.redis_url, decode_responses=True)
        exs = set()
        try:
            cursor = 0
            while True:
                cursor, batch = await redis.scan(cursor=cursor, match="symbols:*", count=200)
                for k in batch or []:
                    parts = (k or "").split(":")
                    if len(parts) >= 2 and parts[0] == "symbols":
                        exs.add(parts[1])
                if cursor == 0:
                    break
        except Exception:
            pass
        try:
            cursor = 0
            while True:
                cursor, batch = await redis.scan(cursor=cursor, match="indicators:*:*:*", count=200)
                for k in batch or []:
                    parts = (k or "").split(":")
                    if len(parts) >= 4 and parts[0] == "indicators":
                        exs.add(parts[1])
                if cursor == 0:
                    break
        except Exception:
            pass
        try:
            cursor = 0
            while True:
                cursor, batch = await redis.scan(cursor=cursor, match="alerts:*:*", count=200)
                for k in batch or []:
                    parts = (k or "").split(":")
                    if len(parts) >= 3 and parts[0] == "alerts":
                        exs.add(parts[1])
                if cursor == 0:
                    break
        except Exception:
            pass
        try:
            cursor = 0
            while True:
                cursor, batch = await redis.scan(cursor=cursor, match="force_stats_stream:*:*", count=200)
                for k in batch or []:
                    parts = (k or "").split(":")
                    if len(parts) >= 3 and parts[0] == "force_stats_stream":
                        exs.add(parts[1])
                if cursor == 0:
                    break
        except Exception:
            pass
        if not exs:
            env_ex = os.getenv("IND_EVENT_EXCHANGE", "")
            if env_ex:
                exs.add(env_ex)
            else:
                exs.add("binance")
        await redis.aclose()
        return sorted(exs)

    exchanges = await _discover_exchanges()
    poll = 60  # 指标事件生成轮询间隔（秒）
    conc = 16  # 指标事件生成并发度（同一交易所并发任务数）

    tasks = []
    for ex in exchanges:
        ac_ex = AlertsConsumer(exchange=ex)
        fsc_ex = ForceStatsConsumer(exchange=ex)
        tasks.extend([
            asyncio.create_task(ac_ex.run()),
            asyncio.create_task(fsc_ex.run()),
            asyncio.create_task(ind_event_run_loop(ex, poll_sec=poll, concurrency=conc)),
        ])
    tasks.extend([
        asyncio.create_task(l0.run()),
        asyncio.create_task(l1.run()),
        asyncio.create_task(fg.run()),
    ])
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
