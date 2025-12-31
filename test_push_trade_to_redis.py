#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：推送交易 JSON 到 Redis

包含4个交易示例：
1. 开多（LONG）
2. 平多（平仓 LONG）
3. 开空（SHORT）
4. 平空（平仓 SHORT）

使用方法：
    python test_push_trade_to_redis.py [示例编号]
    
示例：
    python test_push_trade_to_redis.py 1    # 开多
    python test_push_trade_to_redis.py 2    # 平多
    python test_push_trade_to_redis.py 3    # 开空
    python test_push_trade_to_redis.py 4    # 平空
    python test_push_trade_to_redis.py      # 显示所有示例并选择
"""
import json
import os
import sys
import redis
from typing import Dict, Any, Optional

# Redis 配置（交易队列专用）
REDIS_CONFIG = {
    'host': os.environ.get('TRADE_REDIS_HOST', '101.32.115.249'),
    'port': int(os.environ.get('TRADE_REDIS_PORT', 6379)),
    'password': os.environ.get('TRADE_REDIS_PASSWORD', 'liu146015'),
    'db': int(os.environ.get('TRADE_REDIS_DB', 1)),
    'encoding': 'utf-8',
    'decode_responses': False  # 币安系统使用 bytes 模式
}

TRADE_TASK_NAME = os.environ.get('TRADE_TASK_KEY', 'TASK_ADD_TRADE')

# 默认交易参数（可通过环境变量修改）
DEFAULT_SYMBOL = os.environ.get('TEST_SYMBOL', 'RVVUSDT')  # 交易对
DEFAULT_PRICE = float(os.environ.get('TEST_PRICE', '0.005585'))  # 价格
DEFAULT_AMOUNT = os.environ.get('TEST_AMOUNT', '0.1')  # 数量
DEFAULT_LEVERAGE = float(os.environ.get('TEST_LEVERAGE', '5.0'))  # 杠杆
DEFAULT_TASK_ID = int(os.environ.get('TEST_TASK_ID', '766'))  # 任务ID
DEFAULT_USER_ID = int(os.environ.get('TEST_USER_ID', '2'))  # 用户ID
DEFAULT_API_ID = int(os.environ.get('TEST_API_ID', '0'))  # API ID


def create_trade_json(order_type: str,
                      symbol: str,
                      position_side: str,
                      side: str,
                      price: float,
                      amount: str,
                      leverage: float = 5.0,
                      task_id: int = 0,
                      user_id: int = 2,
                      api_id: int = 0,
                      sl_trigger_px: float = 0.0,
                      tp_trigger_px: float = 0.0,
                      flag: str = "1",
                      api_key: str = "",
                      api_secret: str = "",
                      api_passphrase: str = "",
                      proxies: dict = None) -> Dict[str, Any]:
    """
    创建交易 JSON
    
    Args:
        order_type: 订单类型 ("open", "close", "reduce")
        symbol: 交易对 (如 "ETHUSDT")
        position_side: 持仓方向 ("LONG", "SHORT")
        side: 交易方向 ("BUY", "SELL")
        price: 开仓价格
        amount: 交易数量（字符串）
        leverage: 杠杆倍数
        task_id: 任务ID
        user_id: 用户ID
        api_id: API ID
        sl_trigger_px: 止损价格
        tp_trigger_px: 止盈价格
        flag: 标志 ("0"=实盘, "1"=模拟盘)
        api_key: API Key
        api_secret: API Secret
        api_passphrase: API Passphrase
        proxies: 代理配置
        
    Returns:
        交易 JSON 字典
    """
    trade_json = {
        "order_type": order_type,
        "symbol": symbol,
        "positionSide": position_side,
        "side": side,
        "leverage": float(leverage),
        "sums": str(amount),  # 必须是字符串
        "openAvgPx": float(price),
        "task_id": int(task_id),
        "trader_platform": 2,  # 2=币安
        "follow_type": 2,
        "uniqueName": "ai_trading_system",
        "role_type": 1,
        "reduce_ratio": 0.0,
        "multiple": 1.0,
        "ratio": 0.0,
        "lever_set": 1,
        "first_order_set": 1,
        "api_id": int(api_id),
        "user_id": int(user_id),
        "fast_mode": 1,
        "investment": 100.0,
        "benchMark": 100.0,
        "trade_trigger_mode": 0,
        "sl_trigger_px": float(sl_trigger_px),
        "tp_trigger_px": float(tp_trigger_px),
        "acc": {
            "key": api_key,
            "secret": api_secret,
            "passphrase": api_passphrase,
            "proxies": proxies or {},
            "exchange": 2  # 2=币安
        },
        "flag": flag,  # "0"=实盘, "1"=模拟盘
        "ip_id": 1,
        "posSide_set": 1,
        "pos_mode": 0,
        "pos_value": position_side.lower(),  # "long" 或 "short"
        "vol24h_mode": 0,
        "vol24h_num": 10,
        "white_list_mode": 0,
        "white_list": [],
        "black_list_mode": 0,
        "black_list": [],
        "balance_monitor_mode": 0,
        "balance_monitor_value": 1000.0,
        "private_set": 0
    }

    return trade_json


def create_example_1_open_long() -> Dict[str, Any]:
    """示例1: 开多（LONG）"""
    return create_trade_json(
        order_type="open",
        symbol=DEFAULT_SYMBOL,
        position_side="LONG",
        side="BUY",
        price=DEFAULT_PRICE,
        amount=DEFAULT_AMOUNT,
        leverage=DEFAULT_LEVERAGE,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        sl_trigger_px=DEFAULT_PRICE * 0.98,  # 止损：价格下方2%
        tp_trigger_px=DEFAULT_PRICE * 1.05,  # 止盈：价格上方5%
        flag="1"  # 模拟盘
    )


def create_example_2_close_long() -> Dict[str, Any]:
    """示例2: 平多（平仓 LONG）"""
    return create_trade_json(
        order_type="close",
        symbol=DEFAULT_SYMBOL,
        position_side="LONG",
        side="SELL",  # 平多需要卖出
        price=DEFAULT_PRICE,
        amount=DEFAULT_AMOUNT,
        leverage=DEFAULT_LEVERAGE,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        flag="1"  # 模拟盘
    )


def create_example_3_open_short() -> Dict[str, Any]:
    """示例3: 开空（SHORT）"""
    return create_trade_json(
        order_type="open",
        symbol=DEFAULT_SYMBOL,
        position_side="SHORT",
        side="SELL",
        price=DEFAULT_PRICE,
        amount=DEFAULT_AMOUNT,
        leverage=DEFAULT_LEVERAGE,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        sl_trigger_px=DEFAULT_PRICE * 1.02,  # 止损：价格上方2%
        tp_trigger_px=DEFAULT_PRICE * 0.95,  # 止盈：价格下方5%
        flag="1"  # 模拟盘
    )


def create_example_4_close_short() -> Dict[str, Any]:
    """示例4: 平空（平仓 SHORT）"""
    return create_trade_json(
        order_type="close",
        symbol=DEFAULT_SYMBOL,
        position_side="SHORT",
        side="BUY",  # 平空需要买入
        price=DEFAULT_PRICE,
        amount=DEFAULT_AMOUNT,
        leverage=DEFAULT_LEVERAGE,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        flag="1"  # 模拟盘
    )


def connect_redis(redis_config: Dict) -> Optional[redis.Redis]:
    """
    连接 Redis
    
    Args:
        redis_config: Redis 配置字典
        
    Returns:
        Redis 客户端对象，如果连接失败则返回 None
    """
    try:
        r = redis.Redis(host=redis_config['host'],
                        port=redis_config['port'],
                        password=redis_config.get('password'),
                        db=redis_config.get('db', 0),
                        encoding=redis_config.get('encoding', 'utf-8'),
                        decode_responses=redis_config.get(
                            'decode_responses', False),
                        socket_connect_timeout=5,
                        socket_timeout=5)
        # 测试连接
        r.ping()
        print(
            f"✅ Redis 连接成功: {redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}"
        )
        return r
    except redis.exceptions.ConnectionError as e:
        print(f"❌ Redis 连接失败: {e}")
        print(f"   配置: {redis_config['host']}:{redis_config['port']}")
        return None
    except Exception as e:
        print(f"❌ Redis 连接异常: {e}")
        return None


def push_to_redis(trade_json: Dict[str, Any], redis_config: Dict,
                  queue_name: str) -> bool:
    """
    推送交易 JSON 到 Redis 队列
    
    Args:
        trade_json: 交易 JSON 字典
        redis_config: Redis 配置
        queue_name: 队列名称
        
    Returns:
        是否推送成功
    """
    # 连接 Redis
    r = connect_redis(redis_config)
    if not r:
        return False

    try:
        # 将 JSON 对象转换为字符串
        json_str = json.dumps(trade_json, ensure_ascii=False)

        # 推送到队列（LPUSH：左推，后进先出）
        result = r.lpush(queue_name, json_str)

        print(f"✅ 成功推送到 Redis 队列: {queue_name}")
        print(f"   队列长度: {result}")
        print(f"   JSON 大小: {len(json_str)} 字节")

        return True

    except redis.exceptions.RedisError as e:
        print(f"❌ Redis 操作失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if r:
            r.close()


def print_trade_summary(trade_json: Dict[str, Any], example_name: str):
    """
    打印交易摘要信息
    
    Args:
        trade_json: 交易 JSON 字典
        example_name: 示例名称
    """
    print("\n" + "=" * 60)
    print(f"📋 {example_name}")
    print("=" * 60)
    print(f"订单类型: {trade_json.get('order_type', 'N/A')}")
    print(f"交易对: {trade_json.get('symbol', 'N/A')}")
    print(f"持仓方向: {trade_json.get('positionSide', 'N/A')}")
    print(f"交易方向: {trade_json.get('side', 'N/A')}")
    print(f"杠杆: {trade_json.get('leverage', 'N/A')}")
    print(f"数量: {trade_json.get('sums', 'N/A')}")
    print(f"开仓价格: {trade_json.get('openAvgPx', 'N/A')}")
    print(f"止损价格: {trade_json.get('sl_trigger_px', 'N/A')}")
    print(f"止盈价格: {trade_json.get('tp_trigger_px', 'N/A')}")
    print(f"任务ID: {trade_json.get('task_id', 'N/A')}")
    print(f"用户ID: {trade_json.get('user_id', 'N/A')}")
    print(f"API ID: {trade_json.get('api_id', 'N/A')}")
    print(f"标志: {trade_json.get('flag', 'N/A')} (0=实盘, 1=模拟盘)")
    print("=" * 60 + "\n")


def print_all_examples():
    """打印所有示例的 JSON"""
    examples = [
        ("示例1: 开多（LONG）", create_example_1_open_long),
        ("示例2: 平多（平仓 LONG）", create_example_2_close_long),
        ("示例3: 开空（SHORT）", create_example_3_open_short),
        ("示例4: 平空（平仓 SHORT）", create_example_4_close_short),
    ]

    print("\n" + "=" * 80)
    print("📄 所有交易示例 JSON")
    print("=" * 80)

    for name, func in examples:
        trade_json = func()
        print(f"\n{name}:")
        print(json.dumps(trade_json, indent=2, ensure_ascii=False))
        print("-" * 80)


def main():
    """主函数"""
    print(f"\n🚀 测试推送交易 JSON 到 Redis")
    print(f"   Redis: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
    print(f"   队列: {TRADE_TASK_NAME}")
    print(f"   交易对: {DEFAULT_SYMBOL}")
    print(f"   价格: {DEFAULT_PRICE}")
    print(f"   数量: {DEFAULT_AMOUNT}")
    print(f"   杠杆: {DEFAULT_LEVERAGE}x\n")

    # 示例映射
    examples = {
        "1": ("示例1: 开多（LONG）", create_example_1_open_long),
        "2": ("示例2: 平多（平仓 LONG）", create_example_2_close_long),
        "3": ("示例3: 开空（SHORT）", create_example_3_open_short),
        "4": ("示例4: 平空（平仓 SHORT）", create_example_4_close_short),
    }

    # 解析命令行参数
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        # 显示菜单
        print("请选择要测试的示例：")
        print("  1. 开多（LONG）")
        print("  2. 平多（平仓 LONG）")
        print("  3. 开空（SHORT）")
        print("  4. 平空（平仓 SHORT）")
        print("  5. 显示所有示例 JSON（不推送）")
        print("  0. 退出")
        choice = input("\n请输入选项 (1-5): ").strip()

    # 处理选择
    if choice == "0":
        print("退出")
        sys.exit(0)
    elif choice == "5":
        print_all_examples()
        sys.exit(0)
    elif choice not in examples:
        print(f"❌ 无效选项: {choice}")
        sys.exit(1)

    # 获取示例
    example_name, example_func = examples[choice]
    trade_json = example_func()

    # 打印交易摘要
    print_trade_summary(trade_json, example_name)

    # 询问用户确认
    print("⚠️  准备推送到 Redis 队列...")
    print("   按 Enter 继续，或 Ctrl+C 取消")
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ 用户取消操作")
        sys.exit(0)

    # 推送到 Redis
    success = push_to_redis(trade_json, REDIS_CONFIG, TRADE_TASK_NAME)

    if success:
        print("\n✅ 测试完成！交易 JSON 已成功推送到 Redis")
        print("\n💡 提示:")
        print("   - 可以使用 Redis 客户端检查队列内容")
        print("   - 队列名称: " + TRADE_TASK_NAME)
        print("   - 检查命令: redis-cli -h {} -p {} -a {} LLEN {}".format(
            REDIS_CONFIG['host'], REDIS_CONFIG['port'],
            REDIS_CONFIG['password'], TRADE_TASK_NAME))
    else:
        print("\n❌ 测试失败！请检查 Redis 连接和配置")
        sys.exit(1)


if __name__ == "__main__":
    main()
