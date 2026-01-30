import asyncio
import json
import os
import sys
import time
from typing import Optional, Set

if __package__:
    from api.application.common.redis_client import redis_client
    from .behavior_output import build_behavior_output
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.common.redis_client import redis_client
    from api.application.apps.background.market_structure.behavioral.behavior_output import build_behavior_output


async def _scan_symbols(exchange: str, client: Optional[object] = None) -> Set[str]:
    cli = client or redis_client
    key = f"symbol:{exchange}"
    try:
        ktype = await cli.type(key)
    except Exception:
        return set()
    if str(ktype) != "set":
        return set()
    try:
        raw = await cli.smembers(key)
        return {str(x) for x in (raw or set())}
    except Exception:
        return set()


async def run_behavior_aggregator(
    exchange: str = "binance",
    poll_interval_s: float = 2.0,
    output_key_prefix: str = "behavior:aggTrade",
    ttl_s: int = 300,
) -> None:
    while True:
        symbols = await _scan_symbols(exchange, redis_client)
        now = int(time.time() * 1000)

        for sym in sorted(list(symbols)):
            try:
                payload = await build_behavior_output(exchange, sym)
                key = f"{output_key_prefix}:{exchange}:{sym}"
                await redis_client.set(key, json.dumps(payload, ensure_ascii=False))
                if ttl_s > 0:
                    await redis_client.expire(key, int(ttl_s))
            except Exception:
                continue

        elapsed_ms = int(time.time() * 1000) - now
        await asyncio.sleep(max(0.1, float(poll_interval_s) - elapsed_ms / 1000.0))


def main() -> None:
    asyncio.run(run_behavior_aggregator())


if __name__ == "__main__":
    main()
