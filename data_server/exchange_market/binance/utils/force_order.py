import asyncio
import json
import time
import os
from data_server.exchange_market.binance.utils.redis_client import (
    get_async_redis,
    key_force_stream,
    key_force_stats,
)


EXPIRE_SECONDS = 180  # 3分钟无新数据则过期

redis_client = get_async_redis()


async def handle_force_order(data: dict):
    """处理单笔强平订单数据"""
    try:
        o = data.get("o", {})
        side = o.get("S")  # BUY / SELL
        symbol = o.get("s")  # 币种
        price = float(o.get("p", 0))
        qty = float(o.get("q", 0))
        ts = int(o.get("T", time.time() * 1000))

        # === 写入 Stream ===
        await redis_client.xadd(
            key_force_stream(symbol),
            {"side": side, "symbol": symbol, "price": price, "qty": qty, "ts": ts},
            maxlen=100
        )

        # === 更新统计 Key ===
        exists = await redis_client.exists(key_force_stats(symbol))
        if exists:
            current = await redis_client.get(key_force_stats(symbol))
            stats = json.loads(current)
            stats[side] = stats.get(side, 0) + 1
        else:
            stats = {"SELL": 0, "BUY": 0, "timestamp": ts, side: 1}

        # 更新 Redis 并设置过期
        await redis_client.set(key_force_stats(symbol), json.dumps(stats), ex=EXPIRE_SECONDS)

        print(f"[更新统计] {symbol} {side} 强平 {qty}@{price}，当前统计: {stats}")

    except Exception as e:
        print(f"[错误] 处理强平数据出错: {e}")


async def simulate_force_orders():
    """模拟交易所推送强平订单"""
    sample_data = {
        "e": "forceOrder",
        "E": int(time.time() * 1000),
        "o": {
            "s": "POLYXUSDT",
            "S": "SELL",
            "o": "LIMIT",
            "f": "IOC",
            "q": "581",
            "p": "0.0836300",
            "ap": "0.0849200",
            "X": "FILLED",
            "l": "581",
            "z": "581",
            "T": int(time.time() * 1000)
        }
    }
    await handle_force_order(sample_data)


async def monitor_liquidation_intensity(symbol: str):
    """定期输出当前市场强平强度"""
    while True:
        stats = await redis_client.get(key_force_stats(symbol))
        if stats:
            stats = json.loads(stats)
            duration = (int(time.time() * 1000) - stats["timestamp"]) / 1000
            total = stats.get("BUY", 0) + stats.get("SELL", 0)
            print(f"[监控] 爆仓统计: {stats} 持续 {duration:.1f}s 总量 {total}")
        else:
            print("[监控] 暂无强平活动。")
        await asyncio.sleep(5)


async def main():
    # 启动模拟 & 监控
    await asyncio.gather(
        simulate_force_orders(),
        monitor_liquidation_intensity()
    )


if __name__ == "__main__":
    asyncio.run(main())
