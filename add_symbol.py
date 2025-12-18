"""
添加交易对到监控列表的脚本
用法: python add_symbol.py BTCUSDT
"""
import sys
import os
import redis

# 从环境变量读取 Redis 配置
REDIS_HOST = os.environ.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
REDIS_DB = int(os.environ.get('REDIS_DB', 1))


def add_symbol(symbol: str):
    """添加交易对到监控列表"""
    try:
        r = redis.Redis(host=REDIS_HOST,
                        port=REDIS_PORT,
                        password=REDIS_PASSWORD,
                        db=REDIS_DB,
                        decode_responses=True)

        # 测试连接
        r.ping()
        print(f"✓ Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

        # 添加交易对
        r.sadd('symbol:binance', symbol.upper())

        # 查看当前监控列表
        symbols = r.smembers('symbol:binance')
        print(f"✓ 已添加 {symbol.upper()} 到监控列表")
        print(f"✓ 当前监控的交易对: {sorted(symbols)}")

    except redis.ConnectionError as e:
        print(f"✗ Redis 连接失败: {e}")
        print(f"  请检查环境变量: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)


def remove_symbol(symbol: str):
    """从监控列表移除交易对"""
    try:
        r = redis.Redis(host=REDIS_HOST,
                        port=REDIS_PORT,
                        password=REDIS_PASSWORD,
                        db=REDIS_DB,
                        decode_responses=True)

        r.srem('symbol:binance', symbol.upper())
        symbols = r.smembers('symbol:binance')
        print(f"✓ 已移除 {symbol.upper()} 从监控列表")
        print(f"✓ 当前监控的交易对: {sorted(symbols)}")

    except Exception as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)


def list_symbols():
    """列出当前监控的交易对"""
    try:
        r = redis.Redis(host=REDIS_HOST,
                        port=REDIS_PORT,
                        password=REDIS_PASSWORD,
                        db=REDIS_DB,
                        decode_responses=True)

        symbols = r.smembers('symbol:binance')
        if symbols:
            print(f"✓ 当前监控的交易对: {sorted(symbols)}")
        else:
            print("✓ 当前没有监控任何交易对")

    except Exception as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法:")
        print("  python add_symbol.py add BTCUSDT    # 添加交易对")
        print("  python add_symbol.py remove BTCUSDT # 移除交易对")
        print("  python add_symbol.py list           # 列出所有交易对")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'add':
        if len(sys.argv) < 3:
            print("✗ 请指定要添加的交易对，例如: python add_symbol.py add BTCUSDT")
            sys.exit(1)
        add_symbol(sys.argv[2])
    elif command == 'remove':
        if len(sys.argv) < 3:
            print("✗ 请指定要移除的交易对，例如: python add_symbol.py remove BTCUSDT")
            sys.exit(1)
        remove_symbol(sys.argv[2])
    elif command == 'list':
        list_symbols()
    else:
        print(f"✗ 未知命令: {command}")
        print("  可用命令: add, remove, list")
        sys.exit(1)
