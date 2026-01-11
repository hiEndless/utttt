#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
精简版限价单测试脚本：推送限价单交易 JSON 到 Redis

只包含实际使用的字段
"""
import json
import os
import sys
import redis
import requests
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_DOWN, ROUND_UP


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
DEFAULT_PRICE = float(os.environ.get('TEST_PRICE', '0.17660'))  # 当前市价（用于计算限价）
DEFAULT_LEVERAGE = float(os.environ.get('TEST_LEVERAGE', '20.0'))
DEFAULT_TASK_ID = int(os.environ.get('TEST_TASK_ID', '23'))
DEFAULT_USER_ID = int(os.environ.get('TEST_USER_ID', '2'))
DEFAULT_API_ID = int(os.environ.get('TEST_API_ID', '0'))

# 交易数量配置（二选一）
# 方式1：指定保证金（推荐）- 根据保证金、杠杆和限价动态计算数量
DEFAULT_MARGIN = float(os.environ.get('TEST_MARGIN', '100.0'))  # 保证金（USDT），如100表示100 USDT
# 方式2：直接指定数量（如果设置了 MARGIN，则优先使用保证金计算）
DEFAULT_AMOUNT = os.environ.get('TEST_AMOUNT', None)  # 直接指定数量（字符串），如果为None则使用保证金计算

# 限价单配置
DEFAULT_LIMIT_PRICE_OFFSET = float(os.environ.get('TEST_LIMIT_PRICE_OFFSET', '0'))

# 限价止盈止损配置（价格模式）
DEFAULT_TRADE_TRIGGER_MODE = int(os.environ.get('TEST_TRADE_TRIGGER_MODE', '1'))
DEFAULT_TP_PERCENT = float(os.environ.get('TEST_TP_PERCENT', '1.0'))
DEFAULT_SL_PERCENT = float(os.environ.get('TEST_SL_PERCENT', '1.0'))


def query_binance_step_size(symbol: str, use_testnet: bool = True) -> Optional[float]:
    """查询币安API获取交易对的实际 stepSize"""
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
        return None
    except Exception as e:
        print(f"⚠️  查询币安 stepSize 失败: {e}")
        return None


def get_symbol_step_size(symbol: str, use_testnet: bool = True) -> float:
    """获取交易对的步长（stepSize）"""
    step_size = query_binance_step_size(symbol, use_testnet)
    if step_size is not None:
        return step_size
    precision_map = {
        "BTCUSDT": 0.001, "ETHUSDT": 0.001, "BNBUSDT": 0.001,
        "SOLUSDT": 0.01, "ADAUSDT": 0.1, "DOGEUSDT": 1.0,
        "BEATUSDT": 1.0, "WIFUSDT": 1.0, "POLUSDT": 1.0,
    }
    return precision_map.get(symbol, 0.01)


def format_quantity(quantity: Any, symbol: str, order_type: str = "open", price: float = None) -> str:
    """格式化交易数量，符合币安精度要求"""
    try:
        step_size = get_symbol_step_size(symbol)
        MIN_NOTIONAL = 5.0
        
        if isinstance(quantity, str):
            quantity_decimal = Decimal(quantity)
        else:
            quantity_decimal = Decimal(str(float(quantity)))
        
        step_decimal = Decimal(str(step_size))
        step_str = str(step_size)
        decimal_places = len(step_str.split('.')[-1].rstrip('0')) if '.' in step_str else 0
        
        rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
        quantize_exp = Decimal('0.' + '0' * (decimal_places - 1) + '1') if decimal_places > 0 else Decimal('1')
        rounded_quantity = quantity_decimal.quantize(quantize_exp, rounding=rounding)
        
        if step_size < 1:
            rounded_quantity = (rounded_quantity // step_decimal) * step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=rounding)
        
        if rounded_quantity <= 0:
            rounded_quantity = step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp, rounding=ROUND_UP)
        
        if price is not None and price > 0:
            notional_value = float(rounded_quantity) * price
            if notional_value < MIN_NOTIONAL:
                min_quantity = Decimal(str(MIN_NOTIONAL / price))
                min_quantity = (min_quantity // step_decimal + Decimal('1')) * step_decimal
                min_quantity = min_quantity.quantize(quantize_exp, rounding=ROUND_UP)
                rounded_quantity = min_quantity
        
        result_str = str(rounded_quantity)
        if decimal_places == 0:
            if '.' in result_str:
                result_str = result_str.split('.')[0]
            return result_str
        
        if '.' in result_str:
            parts = result_str.split('.')
            integer_part = parts[0]
            decimal_part = parts[1].rstrip('0')
            if len(decimal_part) == 0 and decimal_places > 0:
                decimal_part = '0' * decimal_places
            elif len(decimal_part) < decimal_places:
                decimal_part = decimal_part + '0' * (decimal_places - len(decimal_part))
            result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
        else:
            if decimal_places > 0:
                result_str = result_str + '.' + '0' * decimal_places
        
        return result_str
    except Exception as e:
        print(f"⚠️  格式化数量失败: {e}, 使用原始值")
        return str(quantity)


def calculate_limit_price(market_price: float, offset_percent: float) -> float:
    """计算限价单价格"""
    limit_price = market_price * (1 + offset_percent / 100.0)
    return round(limit_price, 8)


def calculate_quantity_from_margin(margin: float, leverage: float, price: float) -> float:
    """
    根据保证金、杠杆和价格计算交易数量（张数）
    
    计算公式：sums = 保证金 * 杠杆 / 价格
    
    Args:
        margin: 保证金（USDT）
        leverage: 杠杆倍数
        price: 价格（限价单使用限价，市价单使用市价）
        
    Returns:
        交易数量（浮点数，需要进一步格式化）
    """
    if price <= 0:
        raise ValueError(f"价格必须大于0，当前价格: {price}")
    if leverage <= 0:
        raise ValueError(f"杠杆必须大于0，当前杠杆: {leverage}")
    if margin <= 0:
        raise ValueError(f"保证金必须大于0，当前保证金: {margin}")
    
    quantity = margin * leverage / price
    return quantity


def create_limit_trade_json(order_type: str,
                           symbol: str,
                           position_side: str,
                           side: str,
                           market_price: float,
                           limit_price: float,
                           leverage: float = 5.0,
                           amount: str = None,
                           margin: float = None,
                           task_id: int = 0,
                           user_id: int = 2,
                           api_id: int = 0,
                           trade_trigger_mode: int = 1,
                           tp_price: float = 0.0,
                           sl_price: float = 0.0,
                           flag: str = "1",
                           api_key: str = "",
                           api_secret: str = "",
                           proxies: dict = None) -> Dict[str, Any]:
    """
    创建精简版限价单交易 JSON（只包含实际使用的字段）
    
    Args:
        order_type: 订单类型 ("open", "close", "reduce")
        symbol: 交易对
        position_side: 持仓方向 ("LONG", "SHORT")
        side: 交易方向 ("BUY", "SELL")
        market_price: 当前市价（用于计算名义价值，检查最小名义价值）
        limit_price: 限价价格（用于计算交易数量）
        leverage: 杠杆倍数
        amount: 交易数量（字符串，可选。如果提供则使用，否则根据保证金计算）
        margin: 保证金（USDT，可选。如果提供则根据保证金、杠杆和限价计算数量）
        task_id: 任务ID
        user_id: 用户ID
        api_id: API ID
        trade_trigger_mode: 止盈止损模式（0=关闭, 1=开启）
        tp_price: 止盈价格（具体价格，不是百分比）
        sl_price: 止损价格（具体价格，不是百分比）
        flag: 标志 ("0"=实盘, "1"=模拟盘)
        api_key: API Key
        api_secret: API Secret
        proxies: 代理配置
    
    优先级：如果提供了 amount，则使用 amount；否则使用 margin 计算数量
    
    计算公式：sums = 保证金 * 杠杆 / 限价
    """
    # 计算交易数量：优先使用直接指定的数量，否则根据保证金和限价计算
    if amount is not None:
        raw_quantity = amount
        print(f"📊 使用直接指定的数量: {amount}")
    elif margin is not None and margin > 0:
        raw_quantity = calculate_quantity_from_margin(margin, leverage, limit_price)
        print(f"📊 根据保证金计算数量: 保证金={margin} USDT, 杠杆={leverage}x, 限价={limit_price}, 数量={raw_quantity:.2f}")
    else:
        raise ValueError("必须提供 amount（数量）或 margin（保证金）之一")
    
    formatted_amount = format_quantity(raw_quantity, symbol, order_type, market_price)
    
    trade_json = {
        # 核心交易字段
        "order_type": order_type,
        "symbol": symbol,
        "positionSide": position_side,
        "side": side,
        "leverage": float(leverage),
        "sums": formatted_amount,
        "openAvgPx": float(limit_price),
        
        # 限价单专用字段
        "limit_price": float(limit_price),
        "order_type_binance": "LIMIT",
        "timeInForce": "GTC",
        
        # 账户标识字段
        "task_id": int(task_id),
        "user_id": int(user_id),
        "api_id": int(api_id),
        
        # 止盈止损字段
        "trade_trigger_mode": int(trade_trigger_mode),
        "tp_trigger_px": float(tp_price),
        "sl_trigger_px": float(sl_price),
        
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


def create_example_1_limit_open_long() -> Dict[str, Any]:
    """示例1: 限价开多（LONG）- 带限价止盈止损"""
    limit_price = calculate_limit_price(DEFAULT_PRICE, DEFAULT_LIMIT_PRICE_OFFSET)
    tp_price = DEFAULT_PRICE * (1 + DEFAULT_TP_PERCENT / 100.0)
    sl_price = DEFAULT_PRICE * (1 - DEFAULT_SL_PERCENT / 100.0)
    
    return create_limit_trade_json(
        order_type="open",
        symbol=DEFAULT_SYMBOL,
        position_side="LONG",
        side="BUY",
        market_price=DEFAULT_PRICE,
        limit_price=limit_price,  # 使用限价计算数量
        leverage=DEFAULT_LEVERAGE,
        amount=DEFAULT_AMOUNT,  # 如果为None，则使用margin计算
        margin=DEFAULT_MARGIN if DEFAULT_AMOUNT is None else None,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,
        tp_price=tp_price,
        sl_price=sl_price,
        flag="1"
    )


def create_example_2_limit_close_long() -> Dict[str, Any]:
    """示例2: 限价平多（平仓 LONG）"""
    limit_price = calculate_limit_price(DEFAULT_PRICE, DEFAULT_LIMIT_PRICE_OFFSET)
    
    return create_limit_trade_json(
        order_type="close",
        symbol=DEFAULT_SYMBOL,
        position_side="LONG",
        side="SELL",
        market_price=DEFAULT_PRICE,
        limit_price=limit_price,  # 使用限价计算数量
        leverage=DEFAULT_LEVERAGE,
        amount=DEFAULT_AMOUNT,  # 如果为None，则使用margin计算
        margin=DEFAULT_MARGIN if DEFAULT_AMOUNT is None else None,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        trade_trigger_mode=0,
        tp_price=0.0,
        sl_price=0.0,
        flag="1"
    )


def create_example_3_limit_open_short() -> Dict[str, Any]:
    """示例3: 限价开空（SHORT）- 带限价止盈止损"""
    limit_price = calculate_limit_price(DEFAULT_PRICE, -DEFAULT_LIMIT_PRICE_OFFSET)
    tp_price = DEFAULT_PRICE * (1 - DEFAULT_TP_PERCENT / 100.0)
    sl_price = DEFAULT_PRICE * (1 + DEFAULT_SL_PERCENT / 100.0)
    
    return create_limit_trade_json(
        order_type="open",
        symbol=DEFAULT_SYMBOL,
        position_side="SHORT",
        side="SELL",
        market_price=DEFAULT_PRICE,
        limit_price=limit_price,  # 使用限价计算数量
        leverage=DEFAULT_LEVERAGE,
        amount=DEFAULT_AMOUNT,  # 如果为None，则使用margin计算
        margin=DEFAULT_MARGIN if DEFAULT_AMOUNT is None else None,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        trade_trigger_mode=DEFAULT_TRADE_TRIGGER_MODE,
        tp_price=tp_price,
        sl_price=sl_price,
        flag="1"
    )


def create_example_4_limit_close_short() -> Dict[str, Any]:
    """示例4: 限价平空（平仓 SHORT）"""
    limit_price = calculate_limit_price(DEFAULT_PRICE, DEFAULT_LIMIT_PRICE_OFFSET)
    
    return create_limit_trade_json(
        order_type="close",
        symbol=DEFAULT_SYMBOL,
        position_side="SHORT",
        side="BUY",
        market_price=DEFAULT_PRICE,
        limit_price=limit_price,  # 使用限价计算数量
        leverage=DEFAULT_LEVERAGE,
        amount=DEFAULT_AMOUNT,  # 如果为None，则使用margin计算
        margin=DEFAULT_MARGIN if DEFAULT_AMOUNT is None else None,
        task_id=DEFAULT_TASK_ID,
        user_id=DEFAULT_USER_ID,
        api_id=DEFAULT_API_ID,
        trade_trigger_mode=0,
        tp_price=0.0,
        sl_price=0.0,
        flag="1"
    )


def connect_redis(redis_config: Dict) -> Optional[redis.Redis]:
    """连接 Redis"""
    try:
        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config.get('password'),
            db=redis_config.get('db', 0),
            encoding=redis_config.get('encoding', 'utf-8'),
            decode_responses=redis_config.get('decode_responses', False),
            socket_connect_timeout=10,
            socket_timeout=10
        )
        r.ping()
        print(f"✅ Redis 连接成功: {redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}")
        return r
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return None


def push_to_redis(trade_json: Dict[str, Any], redis_config: Dict, queue_name: str) -> bool:
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
    print(f"币安订单类型: {trade_json.get('order_type_binance', 'LIMIT')}")
    print(f"交易对: {trade_json.get('symbol', 'N/A')}")
    print(f"持仓方向: {trade_json.get('positionSide', 'N/A')}")
    print(f"交易方向: {trade_json.get('side', 'N/A')}")
    print(f"杠杆: {trade_json.get('leverage', 'N/A')}")
    print(f"数量: {trade_json.get('sums', 'N/A')}")
    print(f"限价价格: {trade_json.get('limit_price', trade_json.get('openAvgPx', 'N/A'))}")
    print(f"timeInForce: {trade_json.get('timeInForce', 'GTC')}")
    print(f"止盈止损模式: {trade_json.get('trade_trigger_mode', 'N/A')} (0=关闭, 1=开启)")
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
    print(f"\n🚀 精简版限价单测试脚本")
    print(f"   Redis: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
    print(f"   队列: {TRADE_TASK_NAME}")
    print(f"   交易对: {DEFAULT_SYMBOL}")
    print(f"   当前市价: {DEFAULT_PRICE}")
    print(f"   杠杆: {DEFAULT_LEVERAGE}x")
    print(f"   限价单价格偏移: {DEFAULT_LIMIT_PRICE_OFFSET}%")
    limit_price = calculate_limit_price(DEFAULT_PRICE, DEFAULT_LIMIT_PRICE_OFFSET)
    print(f"   限价价格: {limit_price}")
    
    # 显示数量计算方式
    if DEFAULT_AMOUNT is not None:
        print(f"   数量: {DEFAULT_AMOUNT} (直接指定)")
    else:
        calculated_quantity = calculate_quantity_from_margin(DEFAULT_MARGIN, DEFAULT_LEVERAGE, limit_price)
        print(f"   保证金: {DEFAULT_MARGIN} USDT")
        print(f"   计算数量: {calculated_quantity:.2f} 张 (保证金 * 杠杆 / 限价 = {DEFAULT_MARGIN} * {DEFAULT_LEVERAGE} / {limit_price})")
    
    print(f"   止盈止损模式: {DEFAULT_TRADE_TRIGGER_MODE} (0=关闭, 1=开启)")
    if DEFAULT_TRADE_TRIGGER_MODE == 1:
        tp_price = DEFAULT_PRICE * (1 + DEFAULT_TP_PERCENT / 100.0)
        sl_price = DEFAULT_PRICE * (1 - DEFAULT_SL_PERCENT / 100.0)
        print(f"   止盈价格: {tp_price:.8f} (当前价格 +{DEFAULT_TP_PERCENT}%)")
        print(f"   止损价格: {sl_price:.8f} (当前价格 -{DEFAULT_SL_PERCENT}%)")
    print()

    examples = {
        "1": ("示例1: 限价开多（LONG）- 带限价止盈止损", create_example_1_limit_open_long),
        "2": ("示例2: 限价平多（平仓 LONG）", create_example_2_limit_close_long),
        "3": ("示例3: 限价开空（SHORT）- 带限价止盈止损", create_example_3_limit_open_short),
        "4": ("示例4: 限价平空（平仓 SHORT）", create_example_4_limit_close_short),
    }

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("请选择要测试的示例：")
        print("  1. 限价开多（LONG）- 带限价止盈止损")
        print("  2. 限价平多（平仓 LONG）")
        print("  3. 限价开空（SHORT）- 带限价止盈止损")
        print("  4. 限价平空（平仓 SHORT）")
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
        print("\n✅ 测试完成！限价单交易 JSON 已成功推送到 Redis")
        print("\n💡 提示:")
        print("   - 限价单会在价格达到限价时成交")
        print("   - 如果设置了止盈止损，会在限价单提交后立即设置条件委托单")
        print("   - 止盈止损使用价格模式（具体价格）")
    else:
        print("\n❌ 测试失败！请检查 Redis 连接和配置")
        sys.exit(1)


if __name__ == "__main__":
    main()

