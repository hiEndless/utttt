"""
查看 BTCUSDT 最新价格的脚本
用法: python check_price.py
"""
import os
import redis
import time
from datetime import datetime

# 从环境变量读取 Redis 配置
REDIS_HOST = os.environ.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_DB = int(os.environ.get('REDIS_DB', 1))


def get_latest_price(symbol: str = 'BTCUSDT'):
    """获取最新价格"""
    try:
        r = redis.Redis(host=REDIS_HOST,
                        port=REDIS_PORT,
                        password=REDIS_PASSWORD,
                        db=REDIS_DB,
                        decode_responses=True)

        # 测试连接
        r.ping()

        # 获取最新价格
        key = f'price:binance:{symbol}'
        price_data = r.hgetall(key)

        if not price_data:
            print(f"✗ 未找到 {symbol} 的价格数据")
            print(f"  请确认:")
            print(f"  1. WebSocket 服务是否正在运行")
            print(f"  2. {symbol} 是否已添加到监控列表")
            return None

        price = float(price_data.get('price', 0))
        ts = int(price_data.get('ts', 0))
        bid_liq = float(price_data.get('bid', 0))
        ask_liq = float(price_data.get('ask', 0))

        # 转换时间戳
        dt = datetime.fromtimestamp(ts / 1000)

        print(f"\n{'='*50}")
        print(f"交易对: {symbol}")
        print(f"最新价格: ${price:,.2f} USDT")
        print(f"更新时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"买盘深度: {bid_liq:,.2f}")
        print(f"卖盘深度: {ask_liq:,.2f}")
        print(f"{'='*50}\n")

        return price

    except redis.ConnectionError as e:
        print(f"✗ Redis 连接失败: {e}")
        print(f"  请检查环境变量: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB")
        return None
    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


def watch_price(symbol: str = 'BTCUSDT', interval: float = 1.0):
    """实时监控价格变化"""
    try:
        r = redis.Redis(host=REDIS_HOST,
                        port=REDIS_PORT,
                        password=REDIS_PASSWORD,
                        db=REDIS_DB,
                        decode_responses=True)

        r.ping()

        print(f"开始监控 {symbol} 价格变化 (每 {interval} 秒更新一次)")
        print("按 Ctrl+C 停止监控\n")

        last_price = None

        while True:
            key = f'price:binance:{symbol}'
            price_data = r.hgetall(key)

            if price_data:
                price = float(price_data.get('price', 0))
                ts = int(price_data.get('ts', 0))
                dt = datetime.fromtimestamp(ts / 1000)

                # 计算价格变化
                change_str = ""
                if last_price is not None:
                    change = price - last_price
                    change_pct = (change / last_price) * 100
                    arrow = "↑" if change > 0 else "↓" if change < 0 else "→"
                    change_str = f" {arrow} {change:+.2f} ({change_pct:+.2f}%)"

                print(
                    f"[{dt.strftime('%H:%M:%S')}] {symbol}: ${price:,.2f}{change_str}"
                )
                last_price = price
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待价格数据...")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n监控已停止")
    except Exception as e:
        print(f"✗ 错误: {e}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'watch':
        # 实时监控模式
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'BTCUSDT'
        watch_price(symbol)
    else:
        # 单次查询模式
        symbol = sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT'
        get_latest_price(symbol)
