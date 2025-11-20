import asyncio
from pprint import pprint

from agent_server.events import EventSignal
from agent_server.runtime import handle_event


async def main():
    event = EventSignal(type="market_spike", payload={"symbol": "BTCUSDT", "change": 5.2}, strength="high")
    result = await handle_event(event)
    pprint(result)


if __name__ == "__main__":
    asyncio.run(main())