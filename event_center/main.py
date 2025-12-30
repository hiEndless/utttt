import asyncio
import os
from event_center.pipeline.l0_processor import L0Processor
from event_center.pipeline.l1_aggregator import L1Aggregator
from event_center.pipeline.final_grader import FinalGrader
from alerts_consumer import AlertsConsumer
from force_stats_consumer import ForceStatsConsumer
from ind_envent_generator import run_loop as ind_event_run_loop
from event_center.config import cfg


async def main():
    l0 = L0Processor()
    l1 = L1Aggregator()
    fg = FinalGrader()
    ac = AlertsConsumer()
    fsc = ForceStatsConsumer()
    ex = os.getenv("IND_EVENT_EXCHANGE", "binance")
    poll = int(os.getenv("IND_EVENT_POLL_SEC", "60"))
    conc = int(os.getenv("IND_EVENT_CONCURRENCY", "16"))
    tasks = [
        asyncio.create_task(ac.run()),
        asyncio.create_task(fsc.run()),
        asyncio.create_task(ind_event_run_loop(ex, poll_sec=poll, concurrency=conc)),
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
