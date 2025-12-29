import os
import sys
import json
import asyncio
import redis
from typing import List, Set
from event_center.config import cfg
from event_center.indicators_event.engine.event_engine import run_event_engine


def _redis_client(db: int | None = None) -> redis.Redis:
    return redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=(db if db is not None else cfg.redis_db),
        password=(cfg.redis_password or None),
        decode_responses=True,
    )


def load_symbols(client: redis.Redis, exchange: str) -> List[str]:
    key = f"symbols:{exchange}"
    try:
        members = client.smembers(key)
        if members:
            return sorted(list(members))
        val = client.get(key)
        if val:
            try:
                data = json.loads(val)
                if isinstance(data, list):
                    return sorted([str(x) for x in data])
                if isinstance(data, dict):
                    return sorted([str(k) for k in data.keys()])
            except Exception:
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    return sorted(parts)
    except Exception:
        pass
    discovered: Set[str] = set()
    try:
        pattern = f"indicators:{exchange}:*:" + "1m"
        for k in client.scan_iter(pattern):
            try:
                parts = k.split(":")
                if len(parts) >= 4:
                    symbol = parts[2]
                    if symbol:
                        discovered.add(symbol)
            except Exception:
                continue
    except Exception:
        pass
    return sorted(list(discovered))


async def _run_one(symbol: str, exchange: str):
    try:
        res = await asyncio.to_thread(run_event_engine, symbol, exchange)
        print(f"[指标事件] 交易所={exchange} 交易对={symbol} 市场状态={res.get('market_state')} 方向={res.get('direction')} 强度={res.get('signal_strength')}")
    except Exception as e:
        print(f"[指标事件] 执行出错 交易所={exchange} 交易对={symbol} 错误={e}")


async def run_loop(exchange: str, poll_sec: int = 60, concurrency: int = 16):
    client = _redis_client()
    sem = asyncio.Semaphore(max(1, concurrency))
    while True:
        try:
            symbols = load_symbols(client, exchange)
            if not symbols:
                print(f"[指标事件] 未发现交易对 交易所={exchange} 即将休眠 {poll_sec} 秒")
                await asyncio.sleep(poll_sec)
                continue
            tasks = []
            for sym in symbols:
                async def _task(s=sym):
                    async with sem:
                        await _run_one(s, exchange)
                tasks.append(asyncio.create_task(_task()))
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"[指标事件] 调度循环异常 交易所={exchange} 错误={e}")
        await asyncio.sleep(poll_sec)


if __name__ == "__main__":
    ex = "binance"
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        ex = sys.argv[1].strip()
    poll = int(os.getenv("IND_EVENT_POLL_SEC", "60"))
    conc = int(os.getenv("IND_EVENT_CONCURRENCY", "16"))
    asyncio.run(run_loop(ex, poll_sec=poll, concurrency=conc))
