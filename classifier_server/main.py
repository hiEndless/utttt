import asyncio
from l0_processor import L0Processor
from l1_aggregator import L1Aggregator
from final_grader import FinalGrader


async def main():
    l0 = L0Processor()
    l1 = L1Aggregator()
    fg = FinalGrader()
    tasks = [
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