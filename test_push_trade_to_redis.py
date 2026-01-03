#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：推送交易 JSON 到 Redis

包含4个交易示例：
1. 开多（LONG）- 带止盈止损
2. 平多（平仓 LONG）
3. 开空（SHORT）- 带止盈止损
4. 平空（平仓 SHORT）

止盈止损配置（百分比模式）：
- trade_trigger_mode: 0=关闭, 1=开启
- tp_trigger_px: 止盈比例（百分比），例如：5.0 表示5%
- sl_trigger_px: 止损比例（百分比），例如：2.0 表示2%

环境变量配置：
- TEST_TRADE_TRIGGER_MODE: 止盈止损模式（默认: 1）
- TEST_TP_TRIGGER_PX: 止盈比例（默认: 5.0）
- TEST_SL_TRIGGER_PX: 止损比例（默认: 2.0）

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
import requests
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN, ROUND_UP


# conda env config vars set REDIS_HOST="38.147.173.111"
# conda env config vars set REDIS_PORT="6379"
# conda env config vars set REDIS_PASSWORD="112233Ww.."
# conda env config vars set REDIS_DB="8"
# Redis 配置（交易队列专用）
REDIS_CONFIG = {
    'host': os.environ.get('TRADE_REDIS_HOST', '38.147.173.111'),
    'port': int(os.environ.get('TRADE_REDIS_PORT', 6379)),
    'password': os.environ.get('TRADE_REDIS_PASSWORD', '112233Ww..'),
    'db': int(os.environ.get('TRADE_REDIS_DB', 8)),
    'encoding': 'utf-8',
    'decode_responses': False  # 币安系统使用 bytes 模式
}

TRADE_TASK_NAME = os.environ.get('TRADE_TASK_KEY', 'TASK_ADD_TRADE')

# 默认交易参数（可通过环境变量修改）
# DEFAULT_SYMBOL = os.environ.get('TEST_SYMBOL', 'OGUSDT')  # 交易对
# DEFAULT_PRICE = float(os.environ.get('TEST_PRICE', '6.853'))  # 价格
DEFAULT_SYMBOL = os.environ.get('TEST_SYMBOL', 'MYXUSDT')  # 交易对
DEFAULT_PRICE = float(os.environ.get('TEST_PRICE', '5.620'))  # 价格
# 默认数量：确保名义价值至少为 5 USDT（币安最小要求）
# 如果价格为 1.223，则至少需要 5 / 1.223 ≈ 4.09，向上取整为 5
DEFAULT_AMOUNT = os.environ.get('TEST_AMOUNT', '100')  # 数量（调整为满足最小名义价值要求）
DEFAULT_LEVERAGE = float(os.environ.get('TEST_LEVERAGE', '20.0'))  # 杠杆
DEFAULT_TASK_ID = int(os.environ.get('TEST_TASK_ID', '23'))  # 任务ID
DEFAULT_USER_ID = int(os.environ.get('TEST_USER_ID', '2'))  # 用户ID
DEFAULT_API_ID = int(os.environ.get('TEST_API_ID', '0'))  # API ID

# 止盈止损配置（百分比模式）
DEFAULT_TRADE_TRIGGER_MODE = int(os.environ.get('TEST_TRADE_TRIGGER_MODE', '1'))  # 止盈止损模式：0=关闭, 1=开启
DEFAULT_TP_TRIGGER_PX = float(os.environ.get('TEST_TP_TRIGGER_PX', '10.0'))  # 止盈比例（百分比），例如：5.0 表示5%
DEFAULT_SL_TRIGGER_PX = float(os.environ.get('TEST_SL_TRIGGER_PX', '20.0'))  # 止损比例（百分比），例如：2.0 表示2%


def query_binance_step_size(symbol: str, use_testnet: bool = True) -> Optional[float]:
    """
    查询币安API获取交易对的实际 stepSize
    
    Args:
        symbol: 交易对
        use_testnet: 是否使用测试网
        
    Returns:
        stepSize，如果查询失败则返回 None
    """
    try:
        base_url = "https://testnet.binancefuture.com" if use_testnet else "https://fapi.binance.com"
        url = f"{base_url}/fapi/v1/exchangeInfo"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for item in data.get('symbols', []):
            if item['symbol'] == symbol:
                for filter_item in item.get('filters', []):
                    if filter_item['filterType'] == 'LOT_SIZE':
                        step_size = filter_item.get('stepSize', '0.001')
                        return float(step_size)
        
        print(f"⚠️  未找到 {symbol} 的 stepSize 信息")
        return None
    except Exception as e:
        print(f"⚠️  查询币安 stepSize 失败: {e}")
        return None


def get_symbol_step_size(symbol: str, use_testnet: bool = True) -> float:
    """
    获取交易对的步长（stepSize）
    
    优先从币安API查询，如果查询失败则使用预设值
    
    Args:
        symbol: 交易对
        use_testnet: 是否使用测试网
        
    Returns:
        stepSize
    """
    # 先尝试从币安API查询
    step_size = query_binance_step_size(symbol, use_testnet)
    if step_size is not None:
        print(f"✅ 从币安API获取 {symbol} 的 stepSize: {step_size}")
        return step_size
    
    # 如果查询失败，使用预设值
    print(f"⚠️  使用预设的 stepSize 值")
    precision_map = {
        "BTCUSDT": 0.001,
        "ETHUSDT": 0.001,
        "BNBUSDT": 0.001,
        "SOLUSDT": 0.01,
        "ADAUSDT": 0.1,
        "DOGEUSDT": 1.0,
        "BEATUSDT": 1.0,  # BEATUSDT 默认使用整数精度（根据错误信息调整）
    }
    
    # 如果币种在映射中，使用映射值
    if symbol in precision_map:
        return precision_map[symbol]
    
    # 默认使用 0.01 (2位小数)，适用于大多数币种
    return 0.01


def format_quantity(quantity: Any, symbol: str, order_type: str = "open", price: float = None) -> str:
    """
    格式化交易数量，符合币安精度要求
    
    Args:
        quantity: 原始数量（可以是字符串、float、int）
        symbol: 交易对
        order_type: 订单类型 ("open", "close", "reduce")
        price: 当前价格（用于计算名义价值，确保满足最小要求）
        
    Returns:
        格式化后的数量字符串
    """
    try:
        # 获取步长
        step_size = get_symbol_step_size(symbol)
        
        # 币安最小名义价值要求（USDT）
        MIN_NOTIONAL = 5.0
        
        # 转换为 Decimal 进行精确计算
        if isinstance(quantity, str):
            quantity_decimal = Decimal(quantity)
        else:
            quantity_decimal = Decimal(str(float(quantity)))
        
        # 计算小数位数
        step_decimal = Decimal(str(step_size))
        step_str = str(step_size)
        
        # 计算小数位数（从 stepSize 中提取）
        if '.' in step_str:
            decimal_places = len(step_str.split('.')[-1].rstrip('0'))
        else:
            decimal_places = 0
        
        # 根据订单类型选择舍入方式
        # 开仓：向下取整（避免超过可用资金）
        # 平仓/减仓：向上取整（确保完全平仓）
        rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
        
        # 将数量对齐到步长
        quantize_exp = Decimal('0.' + '0' * (decimal_places - 1) + '1') if decimal_places > 0 else Decimal('1')
        rounded_quantity = quantity_decimal.quantize(quantize_exp, rounding=rounding)
        
        # 确保数量是 stepSize 的倍数
        if step_size < 1:
            # 对于小数步长，需要对齐
            rounded_quantity = (rounded_quantity // step_decimal) * step_decimal
            # 再次量化到正确的小数位数
            rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=rounding)
        
        # 检查格式化后的数量是否为 0
        # 如果为 0，使用向上取整确保至少为最小交易量
        if rounded_quantity <= 0:
            print(f"⚠️  警告：格式化后数量为 0（原始数量: {quantity}, stepSize: {step_size}）")
            print(f"   使用向上取整，至少为 stepSize: {step_size}")
            # 使用向上取整，至少为 stepSize
            rounded_quantity = step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=ROUND_UP)
            print(f"   调整后数量: {rounded_quantity}")
        
        # 检查名义价值是否满足币安最小要求（5 USDT）
        if price is not None and price > 0:
            notional_value = float(rounded_quantity) * price
            if notional_value < MIN_NOTIONAL:
                print(f"⚠️  警告：名义价值 {notional_value:.2f} USDT 小于最小要求 {MIN_NOTIONAL} USDT")
                # 计算满足最小名义价值所需的数量
                min_quantity = Decimal(str(MIN_NOTIONAL / price))
                # 向上取整到 stepSize 的倍数
                min_quantity = (min_quantity // step_decimal + Decimal('1')) * step_decimal
                min_quantity = min_quantity.quantize(quantize_exp, rounding=ROUND_UP)
                print(f"   调整数量从 {rounded_quantity} 到 {min_quantity}（名义价值: {float(min_quantity) * price:.2f} USDT）")
                rounded_quantity = min_quantity
        
        # 转换为字符串
        result_str = str(rounded_quantity)
        
        # 如果 stepSize 是整数（1.0），则返回整数格式
        if decimal_places == 0:
            # 移除小数点
            if '.' in result_str:
                result_str = result_str.split('.')[0]
            return result_str
        
        # 对于小数精度，确保格式正确
        if '.' in result_str:
            parts = result_str.split('.')
            integer_part = parts[0]
            decimal_part = parts[1].rstrip('0')  # 移除尾随零
            
            # 如果小数部分为空，但需要保留精度，则补零
            if len(decimal_part) == 0 and decimal_places > 0:
                decimal_part = '0' * decimal_places
            elif len(decimal_part) < decimal_places:
                # 补齐到所需精度
                decimal_part = decimal_part + '0' * (decimal_places - len(decimal_part))
            
            result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
        else:
            # 如果没有小数点，但需要小数精度，则添加
            if decimal_places > 0:
                result_str = result_str + '.' + '0' * decimal_places
        
        return result_str
        
    except Exception as e:
        print(f"⚠️  格式化数量失败: {e}, 使用原始值")
        return str(quantity)


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
        trade_trigger_mode: 止盈止损模式，0=关闭, 1=开启（必需，开启后使用百分比模式）
        tp_trigger_px: 止盈比例（百分比），例如：5.0 表示5%（可选，0表示不设置）
        sl_trigger_px: 止损比例（百分比），例如：2.0 表示2%（可选，0表示不设置）
        flag: 标志 ("0"=实盘, "1"=模拟盘)
        api_key: API Key
        api_secret: API Secret
        api_passphrase: API Passphrase
        proxies: 代理配置
        
    Returns:
        交易 JSON 字典
    """
    # 格式化数量（符合币安精度要求，并确保满足最小名义价值）
    formatted_amount = format_quantity(amount, symbol, order_type, price)
    
    trade_json = {
        "order_type": order_type,
        "symbol": symbol,
        "positionSide": position_side,
        "side": side,
        "leverage": float(leverage),
        "sums": formatted_amount,  # 使用格式化后的数量（字符串）
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
        "trade_trigger_mode": int(trade_trigger_mode),  # 0=关闭, 1=开启止盈止损
        "tp_trigger_px": float(tp_trigger_px),  # 止盈比例（百分比）
        "sl_trigger_px": float(sl_trigger_px),  # 止损比例（百分比）
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
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,  # 开启止盈止损
        tp_trigger_px=DEFAULT_TP_TRIGGER_PX,  # 止盈：5%（百分比）
        sl_trigger_px=DEFAULT_SL_TRIGGER_PX,  # 止损：2%（百分比）
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
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,  # 平仓时不需要止盈止损
        tp_trigger_px=0.0,
        sl_trigger_px=0.0,
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
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,  # 开启止盈止损
        tp_trigger_px=DEFAULT_TP_TRIGGER_PX,  # 止盈：5%（百分比）
        sl_trigger_px=DEFAULT_SL_TRIGGER_PX,  # 止损：2%（百分比）
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
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,  # 平仓时不需要止盈止损
        tp_trigger_px=0.0,
        sl_trigger_px=0.0,
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
    print(f"止盈止损模式: {trade_json.get('trade_trigger_mode', 'N/A')} (0=关闭, 1=开启)")
    trigger_mode = trade_json.get('trade_trigger_mode', 0)
    if trigger_mode == 1:
        print(f"止盈比例: {trade_json.get('tp_trigger_px', 'N/A')}%")
        print(f"止损比例: {trade_json.get('sl_trigger_px', 'N/A')}%")
    else:
        print(f"止盈: 未设置")
        print(f"止损: 未设置")
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
    print(f"   杠杆: {DEFAULT_LEVERAGE}x")
    print(f"   止盈止损模式: {DEFAULT_TRADE_TRIGGER_MODE} (0=关闭, 1=开启)")
    if DEFAULT_TRADE_TRIGGER_MODE == 1:
        print(f"   止盈比例: {DEFAULT_TP_TRIGGER_PX}%")
        print(f"   止损比例: {DEFAULT_SL_TRIGGER_PX}%")
    print()

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
