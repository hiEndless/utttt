import asyncio
import json
import time
from data_server.binance.ws_binance.utils.redis_client import (
    get_async_redis,
    key_force_stream,
    key_force_stats,
    key_force_stats_stream,
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

        # === 写入 Stream（保留近100条记录） ===
        await redis_client.xadd(
            key_force_stream(symbol),
            {"side": side, "symbol": symbol, "price": price, "qty": qty, "ts": ts},
            maxlen=100,
        )

        stats_key = key_force_stats(symbol)
        exists = await redis_client.exists(stats_key)

        if exists:
            current = await redis_client.get(stats_key)
            stats = json.loads(current)
        else:
            stats = {
                "SELL": 0,
                "BUY": 0,
                "SELL_QTY": 0.0,
                "BUY_QTY": 0.0,
                "timestamp": ts,
            }

        # === 累加次数和数量 ===
        if side == "SELL":
            stats["SELL"] += 1
            stats["SELL_QTY"] += qty
        elif side == "BUY":
            stats["BUY"] += 1
            stats["BUY_QTY"] += qty

        stats["timestamp"] = ts

        async with redis_client.pipeline(transaction=True) as pipe:
            await pipe.xadd(
                key_force_stats_stream(symbol),
                {
                    "symbol": symbol,
                    "ts": ts,
                    "SELL": stats["SELL"],
                    "BUY": stats["BUY"],
                    "SELL_QTY": stats["SELL_QTY"],
                    "BUY_QTY": stats["BUY_QTY"],
                },
                maxlen=1000,
            )
            await pipe.set(stats_key, json.dumps(stats), ex=EXPIRE_SECONDS)
            await pipe.execute()

        print(
            f"[强平更新] {symbol} {side} {qty}@{price} "
            f"→ 当前统计: SELL={stats['SELL']}({stats['SELL_QTY']:.2f}) | "
            f"BUY={stats['BUY']}({stats['BUY_QTY']:.2f})"
        )

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
