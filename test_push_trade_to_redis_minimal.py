#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
精简版市价单测试脚本：推送交易 JSON 到 Redis

只包含实际使用的字段
"""
import json
import os
import sys
import redis
from typing import Dict, Any, Optional

from agent_server.utils.trade_precision import (
    format_price as tp_format_price,
    format_quantity as tp_format_quantity,
)

# Redis 配置
REDIS_CONFIG = {
    'host': os.environ.get('TRADE_REDIS_HOST', '38.147.173.111'),
    'port': int(os.environ.get('TRADE_REDIS_PORT', 6379)),
    'password': os.environ.get('TRADE_REDIS_PASSWORD', '112233Ww..'),
    'db': int(os.environ.get('TRADE_REDIS_DB', 8)),
    'encoding': 'utf-8',
    'decode_responses': False
}

TRADE_TASK_NAME = os.environ.get('TRADE_TASK_KEY', 'TASK_ADD_TRADE')

# 默认交易参数
DEFAULT_SYMBOL = os.environ.get('TEST_SYMBOL', 'POLUSDT')
DEFAULT_PRICE = float(os.environ.get('TEST_PRICE', '0.10515'))
DEFAULT_AMOUNT = os.environ.get('TEST_AMOUNT', '10000')
DEFAULT_LEVERAGE = float(os.environ.get('TEST_LEVERAGE', '20.0'))
DEFAULT_TASK_ID = int(os.environ.get('TEST_TASK_ID', '23'))
DEFAULT_USER_ID = int(os.environ.get('TEST_USER_ID', '2'))
DEFAULT_API_ID = int(os.environ.get('TEST_API_ID', '0'))

# 止盈止损配置（价格模式，使用具体价格）
DEFAULT_TRADE_TRIGGER_MODE = int(os.environ.get('TEST_TRADE_TRIGGER_MODE',
                                                '1'))
# 如果设置了 TEST_TP_PERCENT 和 TEST_SL_PERCENT，则使用百分比计算价格
# 否则直接使用 TEST_TP_TRIGGER_PX 和 TEST_SL_TRIGGER_PX 作为具体价格
DEFAULT_TP_PERCENT = float(os.environ.get('TEST_TP_PERCENT', '1.0'))  # 止盈百分比
DEFAULT_SL_PERCENT = float(os.environ.get('TEST_SL_PERCENT', '1.0'))  # 止损百分比
DEFAULT_TP_TRIGGER_PX = os.environ.get('TEST_TP_TRIGGER_PX',
                                       None)  # 如果设置，直接使用此价格
DEFAULT_SL_TRIGGER_PX = os.environ.get('TEST_SL_TRIGGER_PX',
                                       None)  # 如果设置，直接使用此价格


def query_binance_step_size(symbol: str,
                            use_testnet: bool = True) -> Optional[float]:
    """
    兼容旧接口，内部已统一到 agent_server.utils.trade_precision
    """
    from agent_server.utils.trade_precision import get_symbol_step_size

    return get_symbol_step_size(symbol, use_testnet)


def get_symbol_step_size(symbol: str, use_testnet: bool = True) -> float:
    """向后兼容封装，内部转到 trade_precision.get_symbol_step_size"""
    from agent_server.utils.trade_precision import get_symbol_step_size as _gss

    return _gss(symbol, use_testnet)


def query_binance_tick_size(symbol: str,
                            use_testnet: bool = True) -> Optional[float]:
    """兼容旧接口，内部已统一到 agent_server.utils.trade_precision"""
    from agent_server.utils.trade_precision import get_symbol_tick_size

    return get_symbol_tick_size(symbol, use_testnet)


def get_symbol_tick_size(symbol: str, use_testnet: bool = True) -> float:
    """向后兼容封装，内部转到 trade_precision.get_symbol_tick_size"""
    from agent_server.utils.trade_precision import get_symbol_tick_size as _gts

    return _gts(symbol, use_testnet)


def format_price(price: float, symbol: str, use_testnet: bool = True) -> str:
    """向后兼容封装，内部转到 trade_precision.format_price"""
    return tp_format_price(price, symbol, use_testnet)


def format_quantity(quantity,
                    symbol: str,
                    order_type: str = "open",
                    price: float = None) -> str:
    """向后兼容封装，内部转到 trade_precision.format_quantity"""
    return tp_format_quantity(quantity,
                              symbol,
                              order_type=order_type,
                              price=price)


def calculate_tp_sl_prices(market_price: float,
                           position_side: str,
                           tp_percent: float = 0.0,
                           sl_percent: float = 0.0,
                           tp_price: Optional[float] = None,
                           sl_price: Optional[float] = None) -> tuple:
    """
    计算止盈止损价格
    
    :param market_price: 市场价格
    :param position_side: 持仓方向 ("LONG", "SHORT")
    :param tp_percent: 止盈百分比（如果提供了tp_price则忽略）
    :param sl_percent: 止损百分比（如果提供了sl_price则忽略）
    :param tp_price: 止盈价格（如果提供则直接使用）
    :param sl_price: 止损价格（如果提供则直接使用）
    :return: (tp_price, sl_price) 元组
    """
    calculated_tp = None
    calculated_sl = None

    if tp_price is not None:
        calculated_tp = tp_price
    elif tp_percent > 0:
        if position_side == "LONG":
            calculated_tp = market_price * (1 + tp_percent / 100.0)
        else:  # SHORT
            calculated_tp = market_price * (1 - tp_percent / 100.0)

    if sl_price is not None:
        calculated_sl = sl_price
    elif sl_percent > 0:
        if position_side == "LONG":
            calculated_sl = market_price * (1 - sl_percent / 100.0)
        else:  # SHORT
            calculated_sl = market_price * (1 + sl_percent / 100.0)

    return calculated_tp, calculated_sl


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
                      trade_trigger_mode: int = 1,
                      tp_trigger_px: float = 0.0,
                      sl_trigger_px: float = 0.0,
                      flag: str = "1",
                      api_key: str = "",
                      api_secret: str = "",
                      proxies: dict = None) -> Dict[str, Any]:
    """
    创建精简版市价单交易 JSON（只包含实际使用的字段）
    
    实际使用的字段：
    - order_type: 订单类型 ("open", "close", "reduce")
    - symbol: 交易对
    - positionSide: 持仓方向 ("LONG", "SHORT")
    - side: 交易方向 ("BUY", "SELL")
    - leverage: 杠杆倍数
    - sums: 交易数量（字符串）
    - openAvgPx: 参考价格（用于计算名义价值）
    - task_id: 任务ID
    - user_id: 用户ID
    - api_id: API ID
    - trade_trigger_mode: 止盈止损模式（0=关闭, 1=开启）
    - tp_trigger_px: 止盈价格（具体价格，不是百分比）
    - sl_trigger_px: 止损价格（具体价格，不是百分比）
    - acc: 账户信息（包含key, secret, proxies, exchange）
    - flag: 标志 ("0"=实盘, "1"=模拟盘)
    - uniqueName: 系统标识（用于日志）
    - status: 任务状态（可选）
    """
    formatted_amount = format_quantity(amount, symbol, order_type, price)

    # 格式化止盈止损价格（确保精度正确）
    formatted_tp = float(
        tp_trigger_px) if tp_trigger_px and tp_trigger_px > 0 else 0.0
    formatted_sl = float(
        sl_trigger_px) if sl_trigger_px and sl_trigger_px > 0 else 0.0

    if formatted_tp > 0:
        formatted_tp = float(format_price(formatted_tp, symbol))
    if formatted_sl > 0:
        formatted_sl = float(format_price(formatted_sl, symbol))

    trade_json = {
        # 核心交易字段
        "order_type": order_type,
        "symbol": symbol,
        "positionSide": position_side,
        "side": side,
        "leverage": float(leverage),
        "sums": formatted_amount,
        "openAvgPx": float(price),

        # 账户标识字段
        "task_id": int(task_id),
        "user_id": int(user_id),
        "api_id": int(api_id),

        # 止盈止损字段（使用具体价格）
        "trade_trigger_mode": int(trade_trigger_mode),
        "tp_trigger_px": formatted_tp,
        "sl_trigger_px": formatted_sl,

        # 账户信息
        "acc": {
            "key": api_key,
            "secret": api_secret,
            "passphrase": "",
            "proxies": proxies or {},
            "exchange": 2  # 2=币安
        },

        # 系统标识
        "flag": flag,
        "uniqueName": "ai_trading_system",

        # 可选字段（如果提供则使用，否则从数据库获取）
        # "ip_id": 1,  # 如果不提供，会从数据库获取
        # "status": 1,  # 任务状态（可选）
    }

    return trade_json


def create_example_1_open_long() -> Dict[str, Any]:
    """示例1: 市价开多（LONG）- 带止盈止损"""
    # 计算止盈止损价格
    if DEFAULT_TP_TRIGGER_PX is not None and DEFAULT_SL_TRIGGER_PX is not None:
        # 直接使用提供的价格
        tp_price = float(DEFAULT_TP_TRIGGER_PX)
        sl_price = float(DEFAULT_SL_TRIGGER_PX)
    else:
        # 使用百分比计算价格
        tp_price, sl_price = calculate_tp_sl_prices(
            market_price=DEFAULT_PRICE,
            position_side="LONG",
            tp_percent=DEFAULT_TP_PERCENT,
            sl_percent=DEFAULT_SL_PERCENT)
        tp_price = tp_price if tp_price else 0.0
        sl_price = sl_price if sl_price else 0.0

    return create_trade_json(order_type="open",
                             symbol=DEFAULT_SYMBOL,
                             position_side="LONG",
                             side="BUY",
                             price=DEFAULT_PRICE,
                             amount=DEFAULT_AMOUNT,
                             leverage=DEFAULT_LEVERAGE,
                             task_id=DEFAULT_TASK_ID,
                             user_id=DEFAULT_USER_ID,
                             api_id=DEFAULT_API_ID,
                             trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,
                             tp_trigger_px=tp_price,
                             sl_trigger_px=sl_price,
                             flag="1")


def create_example_2_close_long() -> Dict[str, Any]:
    """示例2: 市价平多（平仓 LONG）"""
    return create_trade_json(order_type="close",
                             symbol=DEFAULT_SYMBOL,
                             position_side="LONG",
                             side="SELL",
                             price=DEFAULT_PRICE,
                             amount=DEFAULT_AMOUNT,
                             leverage=DEFAULT_LEVERAGE,
                             task_id=DEFAULT_TASK_ID,
                             user_id=DEFAULT_USER_ID,
                             api_id=DEFAULT_API_ID,
                             trade_trigger_mode=0,
                             tp_trigger_px=0.0,
                             sl_trigger_px=0.0,
                             flag="1")


def create_example_3_open_short() -> Dict[str, Any]:
    """示例3: 市价开空（SHORT）- 带止盈止损"""
    # 计算止盈止损价格
    if DEFAULT_TP_TRIGGER_PX is not None and DEFAULT_SL_TRIGGER_PX is not None:
        # 直接使用提供的价格
        tp_price = float(DEFAULT_TP_TRIGGER_PX)
        sl_price = float(DEFAULT_SL_TRIGGER_PX)
    else:
        # 使用百分比计算价格
        tp_price, sl_price = calculate_tp_sl_prices(
            market_price=DEFAULT_PRICE,
            position_side="SHORT",
            tp_percent=DEFAULT_TP_PERCENT,
            sl_percent=DEFAULT_SL_PERCENT)
        tp_price = tp_price if tp_price else 0.0
        sl_price = sl_price if sl_price else 0.0

    return create_trade_json(order_type="open",
                             symbol=DEFAULT_SYMBOL,
                             position_side="SHORT",
                             side="SELL",
                             price=DEFAULT_PRICE,
                             amount=DEFAULT_AMOUNT,
                             leverage=DEFAULT_LEVERAGE,
                             task_id=DEFAULT_TASK_ID,
                             user_id=DEFAULT_USER_ID,
                             api_id=DEFAULT_API_ID,
                             trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,
                             tp_trigger_px=tp_price,
                             sl_trigger_px=sl_price,
                             flag="1")


def create_example_4_close_short() -> Dict[str, Any]:
    """示例4: 市价平空（平仓 SHORT）"""
    return create_trade_json(order_type="close",
                             symbol=DEFAULT_SYMBOL,
                             position_side="SHORT",
                             side="BUY",
                             price=DEFAULT_PRICE,
                             amount=DEFAULT_AMOUNT,
                             leverage=DEFAULT_LEVERAGE,
                             task_id=DEFAULT_TASK_ID,
                             user_id=DEFAULT_USER_ID,
                             api_id=DEFAULT_API_ID,
                             trade_trigger_mode=0,
                             tp_trigger_px=0.0,
                             sl_trigger_px=0.0,
                             flag="1")


def connect_redis(redis_config: Dict) -> Optional[redis.Redis]:
    """连接 Redis"""
    try:
        r = redis.Redis(host=redis_config['host'],
                        port=redis_config['port'],
                        password=redis_config.get('password'),
                        db=redis_config.get('db', 0),
                        encoding=redis_config.get('encoding', 'utf-8'),
                        decode_responses=redis_config.get(
                            'decode_responses', False),
                        socket_connect_timeout=10,
                        socket_timeout=10)
        r.ping()
        print(
            f"✅ Redis 连接成功: {redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}"
        )
        return r
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return None


def push_to_redis(trade_json: Dict[str, Any], redis_config: Dict,
                  queue_name: str) -> bool:
    """推送交易 JSON 到 Redis 队列"""
    r = connect_redis(redis_config)
    if not r:
        return False

    try:
        json_str = json.dumps(trade_json, ensure_ascii=False)
        result = r.lpush(queue_name, json_str)
        print(f"✅ 成功推送到 Redis 队列: {queue_name}")
        print(f"   队列长度: {result}")
        print(f"   JSON 大小: {len(json_str)} 字节")
        return True
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        return False
    finally:
        if r:
            r.close()


def print_trade_summary(trade_json: Dict[str, Any], example_name: str):
    """打印交易摘要信息"""
    print("\n" + "=" * 60)
    print(f"📋 {example_name}")
    print("=" * 60)
    print(f"订单类型: {trade_json.get('order_type', 'N/A')}")
    print(f"交易对: {trade_json.get('symbol', 'N/A')}")
    print(f"持仓方向: {trade_json.get('positionSide', 'N/A')}")
    print(f"交易方向: {trade_json.get('side', 'N/A')}")
    print(f"杠杆: {trade_json.get('leverage', 'N/A')}")
    print(f"数量: {trade_json.get('sums', 'N/A')}")
    print(f"参考价格: {trade_json.get('openAvgPx', 'N/A')}")
    print(
        f"止盈止损模式: {trade_json.get('trade_trigger_mode', 'N/A')} (0=关闭, 1=开启)")
    trigger_mode = trade_json.get('trade_trigger_mode', 0)
    if trigger_mode == 1:
        print(f"止盈价格: {trade_json.get('tp_trigger_px', 'N/A')}")
        print(f"止损价格: {trade_json.get('sl_trigger_px', 'N/A')}")
    else:
        print(f"止盈: 未设置")
        print(f"止损: 未设置")
    print(f"任务ID: {trade_json.get('task_id', 'N/A')}")
    print(f"用户ID: {trade_json.get('user_id', 'N/A')}")
    print(f"API ID: {trade_json.get('api_id', 'N/A')}")
    print(f"标志: {trade_json.get('flag', 'N/A')} (0=实盘, 1=模拟盘)")
    print("=" * 60 + "\n")


def main():
    """主函数"""
    print(f"\n🚀 精简版市价单测试脚本")
    print(f"   Redis: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
    print(f"   队列: {TRADE_TASK_NAME}")
    print(f"   交易对: {DEFAULT_SYMBOL}")
    print(f"   价格: {DEFAULT_PRICE}")
    print(f"   数量: {DEFAULT_AMOUNT}")
    print(f"   杠杆: {DEFAULT_LEVERAGE}x")
    print(f"   止盈止损模式: {DEFAULT_TRADE_TRIGGER_MODE} (0=关闭, 1=开启)")
    if DEFAULT_TRADE_TRIGGER_MODE == 1:
        if DEFAULT_TP_TRIGGER_PX is not None and DEFAULT_SL_TRIGGER_PX is not None:
            print(f"   止盈价格: {DEFAULT_TP_TRIGGER_PX}")
            print(f"   止损价格: {DEFAULT_SL_TRIGGER_PX}")
        else:
            print(f"   止盈比例: {DEFAULT_TP_PERCENT}%")
            print(f"   止损比例: {DEFAULT_SL_PERCENT}%")
            # 计算示例价格（LONG方向）
            tp_price, sl_price = calculate_tp_sl_prices(
                market_price=DEFAULT_PRICE,
                position_side="LONG",
                tp_percent=DEFAULT_TP_PERCENT,
                sl_percent=DEFAULT_SL_PERCENT)
            if tp_price:
                print(
                    f"   止盈价格（LONG示例）: {format_price(tp_price, DEFAULT_SYMBOL)}"
                )
            if sl_price:
                print(
                    f"   止损价格（LONG示例）: {format_price(sl_price, DEFAULT_SYMBOL)}"
                )
    print()

    examples = {
        "1": ("示例1: 市价开多（LONG）- 带止盈止损", create_example_1_open_long),
        "2": ("示例2: 市价平多（平仓 LONG）", create_example_2_close_long),
        "3": ("示例3: 市价开空（SHORT）- 带止盈止损", create_example_3_open_short),
        "4": ("示例4: 市价平空（平仓 SHORT）", create_example_4_close_short),
    }

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("请选择要测试的示例：")
        print("  1. 市价开多（LONG）- 带止盈止损")
        print("  2. 市价平多（平仓 LONG）")
        print("  3. 市价开空（SHORT）- 带止盈止损")
        print("  4. 市价平空（平仓 SHORT）")
        print("  0. 退出")
        choice = input("\n请输入选项 (1-4): ").strip()

    if choice == "0":
        print("退出")
        sys.exit(0)
    elif choice not in examples:
        print(f"❌ 无效选项: {choice}")
        sys.exit(1)

    example_name, example_func = examples[choice]
    trade_json = example_func()

    print_trade_summary(trade_json, example_name)

    success = push_to_redis(trade_json, REDIS_CONFIG, TRADE_TASK_NAME)

    if success:
        print("\n✅ 测试完成！市价单交易 JSON 已成功推送到 Redis")
        print("\n💡 提示:")
        print("   - 市价单会立即按当前市价成交")
        print("   - 如果设置了止盈止损，会在开仓后自动设置")
        print("   - 止盈止损使用价格模式（具体价格，已格式化精度）")
    else:
        print("\n❌ 测试失败！请检查 Redis 连接和配置")
        sys.exit(1)


if __name__ == "__main__":
    main()
