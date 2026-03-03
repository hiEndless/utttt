"""
Redis数据验证脚本
用于验证force_stats和aggtrades数据是否正常
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent_server.utils.redis_client import get_redis_client


async def verify_force_stats(symbol: str = "ETHUSDT"):
    """验证force_stats数据"""
    print(f"\n{'='*60}")
    print(f"验证 force_stats:binance:{symbol}")
    print(f"{'='*60}")

    client = get_redis_client()
    key = f"force_stats:binance:{symbol}"

    try:
        raw = await client.get(key)
        if raw is None:
            print(f"❌ Key不存在: {key}")
            return None

        print(f"✅ Key存在: {key}")

        # 尝试解析数据
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                print(f"⚠️  数据不是JSON格式，原始数据: {raw[:200]}")
                return None
        else:
            data = raw

        print(f"\n数据内容:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # 检查关键字段
        required_fields = ["SELL", "BUY", "SELL_QTY", "BUY_QTY", "timestamp"]
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            print(f"\n⚠️  缺少字段: {missing_fields}")
        else:
            print(f"\n✅ 所有必需字段都存在")

        return data

    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def verify_aggtrades(symbol: str = "BTCUSDT", limit: int = 10):
    """验证aggtrades流数据"""
    print(f"\n{'='*60}")
    print(f"验证 aggtrades:binance:{symbol} (最近{limit}条)")
    print(f"{'='*60}")

    client = get_redis_client()
    key = f"aggtrades:binance:{symbol}"

    try:
        # 检查key是否存在
        exists = await client.exists(key)
        if not exists:
            print(f"❌ Key不存在: {key}")
            return None

        print(f"✅ Key存在: {key}")

        # 读取流数据
        # xrevrange 从最新到最旧，max="+", min="-" 表示所有数据
        rows = await client.xrevrange(key, max="+", min="-", count=limit)

        if not rows:
            print(f"⚠️  流中没有数据")
            return None

        print(f"\n✅ 找到 {len(rows)} 条数据\n")

        # 显示最近几条数据
        for i, (entry_id, fields) in enumerate(rows[:limit], 1):
            print(f"--- 记录 {i} (ID: {entry_id}) ---")
            if isinstance(fields, dict):
                ts = fields.get("ts", "N/A")
                price = fields.get("price", "N/A")
                qty = fields.get("qty", "N/A")
                is_buyer_maker = fields.get("is_buyer_maker", "N/A")

                # 计算价值
                try:
                    value_usdt = float(price) * float(qty)
                    direction = "卖出" if int(is_buyer_maker) else "买入"
                    print(f"  时间戳: {ts}")
                    print(f"  价格: {price}")
                    print(f"  数量: {qty}")
                    print(
                        f"  方向: {direction} (is_buyer_maker={is_buyer_maker})")
                    print(f"  价值: ${value_usdt:,.2f} USDT")
                except:
                    print(f"  原始数据: {fields}")
            else:
                print(f"  原始数据: {fields}")
            print()

        return rows

    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def verify_aggtrades_with_time_window(symbol: str = "BTCUSDT",
                                            window_ms: int = 60000):
    """验证aggtrades流数据（带时间窗口）"""
    print(f"\n{'='*60}")
    print(f"验证 aggtrades:binance:{symbol} (时间窗口: {window_ms}ms)")
    print(f"{'='*60}")

    import time
    client = get_redis_client()
    key = f"aggtrades:binance:{symbol}"

    try:
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - window_ms

        print(
            f"当前时间: {now_ms} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ms/1000))})"
        )
        print(
            f"起始时间: {since_ms} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(since_ms/1000))})"
        )

        # 读取所有数据
        rows = await client.xrevrange(key, max="+", min="-", count=10000)

        if not rows:
            print(f"⚠️  流中没有数据")
            return None

        print(f"\n✅ 流中共有 {len(rows)} 条数据")

        # 过滤时间窗口内的数据
        window_data = []
        large_orders = []

        for entry_id, fields in reversed(rows):
            if not isinstance(fields, dict):
                continue

            try:
                ts = int(float(fields.get("ts", 0)))
                if ts < since_ms:
                    continue

                price = float(fields.get("price", 0))
                qty = float(fields.get("qty", 0))
                is_buyer_maker = bool(int(fields.get("is_buyer_maker", 0)))

                if price <= 0 or qty <= 0:
                    continue

                value_usdt = price * qty
                window_data.append({
                    "ts": ts,
                    "price": price,
                    "qty": qty,
                    "value_usdt": value_usdt,
                    "is_buyer_maker": is_buyer_maker,
                })

                # 检查是否为大订单（阈值1000 USDT）
                if value_usdt >= 1000.0:
                    large_orders.append({
                        "ts":
                        ts,
                        "price":
                        price,
                        "qty":
                        qty,
                        "value_usdt":
                        value_usdt,
                        "direction":
                        "卖出" if is_buyer_maker else "买入",
                    })

            except Exception as e:
                continue

        print(f"\n时间窗口内数据: {len(window_data)} 条")
        print(f"大订单数量: {len(large_orders)} 条 (≥$1000)")

        if large_orders:
            print(f"\n大订单详情:")
            for order in large_orders[:10]:  # 只显示前10条
                ts_str = time.strftime('%H:%M:%S',
                                       time.localtime(order['ts'] / 1000))
                print(
                    f"  {ts_str} | {order['direction']:4s} | ${order['value_usdt']:>10,.2f} | {order['qty']:>12.8f} @ {order['price']:.8f}"
                )
        else:
            print(f"\n⚠️  时间窗口内没有大订单（≥$1000）")

        # 统计买卖方向
        buy_value = sum(o['value_usdt'] for o in window_data
                        if not o['is_buyer_maker'])
        sell_value = sum(o['value_usdt'] for o in window_data
                         if o['is_buyer_maker'])

        print(f"\n买卖统计:")
        print(f"  买入总额: ${buy_value:,.2f}")
        print(f"  卖出总额: ${sell_value:,.2f}")
        if sell_value > 0:
            buy_sell_ratio = buy_value / sell_value
            print(f"  买卖比例: {buy_sell_ratio:.2f} (>1表示买入主导)")
        else:
            print(f"  买卖比例: N/A (无卖出数据)")

        return {
            "window_data": window_data,
            "large_orders": large_orders,
            "buy_value": buy_value,
            "sell_value": sell_value,
        }

    except Exception as e:
        print(f"❌ 读取失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def check_redis_config():
    """检查Redis配置"""
    print(f"\n{'='*60}")
    print("检查Redis配置")
    print(f"{'='*60}")

    from agent_server.config import settings

    print(f"Redis Host: {settings.redis_host}")
    print(f"Redis Port: {settings.redis_port}")
    print(f"Redis DB: {settings.redis_db}")
    print(f"Redis Password: {'***' if settings.redis_password else 'None'}")

    # 测试连接
    try:
        client = get_redis_client()
        info = await client.info()
        print(f"\n✅ Redis连接成功")
        print(f"Redis版本: {info.get('redis_version', 'N/A')}")
        print(f"已使用内存: {info.get('used_memory_human', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Redis连接失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Redis数据验证工具")
    print("=" * 60)

    # 检查配置
    await check_redis_config()

    # 验证force_stats
    await verify_force_stats("ETHUSDT")
    await verify_force_stats("PIPPINUSDT")

    # 验证aggtrades
    await verify_aggtrades("BTCUSDT", limit=5)
    await verify_aggtrades("PIPPINUSDT", limit=5)

    # 验证aggtrades（带时间窗口）
    await verify_aggtrades_with_time_window("BTCUSDT", window_ms=60000)
    await verify_aggtrades_with_time_window("PIPPINUSDT", window_ms=60000)

    print(f"\n{'='*60}")
    print("验证完成")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
