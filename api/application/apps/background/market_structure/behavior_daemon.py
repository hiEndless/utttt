import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set

if __package__:
    from .behavior_output import build_behavior_output
    from ....common.redis_client import redis_client
else:
    _d = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_d, "..", "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from api.application.apps.background.market_structure.behavior_output import build_behavior_output
    from api.application.common.redis_client import redis_client


async def _scan_symbols(exchange: str, client: Optional[object] = None) -> Set[str]:
    """读取 data_server 使用的 symbol set，便于在后台聚合保持一致。"""
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
    """后台守护：周期读取 aggTrade stream，生成行为结构，并落到 Redis JSON key。"""
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
    """本地运行：python -m api.application.apps.background.market_structure.behavior_daemon"""
    asyncio.run(run_behavior_aggregator())


if __name__ == "__main__":
    main()

