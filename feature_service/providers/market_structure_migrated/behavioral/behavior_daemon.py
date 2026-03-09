import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional, Set

if __package__:
    from feature_service.providers.market_structure_migrated.utils.redis_client import get_redis_client
    from .behavior_output import build_behavior_output
else:
    # 兼容“直接 python 运行脚本”的场景：向上查找包含 feature_service 的仓库根目录并加入 sys.path
    _root = None
    for p in Path(__file__).resolve().parents:
        if (p / "feature_service").is_dir():
            _root = str(p)
            break
    if _root and _root not in sys.path:
        sys.path.insert(0, _root)
    from feature_service.providers.market_structure_migrated.utils.redis_client import get_redis_client
    from feature_service.providers.market_structure_migrated.behavioral.behavior_output import build_behavior_output

# 统一使用 feature_service 迁移层 Redis 连接，避免跨模块重复初始化导致的不一致
redis_client = get_redis_client()


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
