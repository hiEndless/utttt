"""
统一的交易精度工具：数量(stepSize) 与价格(tickSize) 处理

供 Trade Agent 与交易服务侧脚本共同使用，确保数量/价格格式一致，避免 Binance -1111 精度错误。

设计要点：
- 优先尝试从 Binance exchangeInfo 获取真实 stepSize / tickSize（带简单内存缓存）
- 若获取失败，则回退到常见交易对的本地映射表
- 对数量使用 LOT_SIZE 步长截断，并确保名义价值不少于 MIN_NOTIONAL
- 对价格使用 PRICE_FILTER tickSize 截断
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Any, Optional, Dict

import requests

logger = logging.getLogger(__name__)

# 简单的内存缓存，避免重复拉取 exchangeInfo
_EXCHANGE_INFO_CACHE: Dict[str, dict] = {}


def _get_exchange_info(use_testnet: bool = True) -> Optional[dict]:
    """获取并缓存 Binance exchangeInfo"""
    key = "testnet" if use_testnet else "prod"
    if key in _EXCHANGE_INFO_CACHE:
        return _EXCHANGE_INFO_CACHE[key]

    base_url = "https://testnet.binancefuture.com" if use_testnet else "https://fapi.binance.com"
    url = f"{base_url}/fapi/v1/exchangeInfo"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _EXCHANGE_INFO_CACHE[key] = data
        return data
    except Exception as e:
        logger.warning("query_exchange_info_failed use_testnet=%s error=%s",
                       use_testnet, e)
        return None


def query_binance_step_size(symbol: str,
                            use_testnet: bool = True) -> Optional[float]:
    """从 exchangeInfo 查询某个 symbol 的 LOT_SIZE.stepSize"""
    info = _get_exchange_info(use_testnet)
    if not info:
        return None
    try:
        for item in info.get("symbols", []):
            if item.get("symbol") == symbol:
                for f in item.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step_size = f.get("stepSize", "0.001")
                        return float(step_size)
    except Exception as e:
        logger.warning("query_step_size_failed symbol=%s error=%s", symbol, e)
    return None


def get_symbol_step_size(symbol: str, use_testnet: bool = True) -> float:
    """获取交易对步长（stepSize），优先从 Binance 查询，失败则使用本地映射"""
    step = query_binance_step_size(symbol, use_testnet)
    if step is not None:
        return step

    # 本地兜底映射（来自测试脚本）
    precision_map = {
        "BTCUSDT": 0.001,
        "ETHUSDT": 0.001,
        "BNBUSDT": 0.001,
        "SOLUSDT": 0.01,
        "ADAUSDT": 0.1,
        "DOGEUSDT": 1.0,
        "BEATUSDT": 1.0,
        "WIFUSDT": 1.0,
        "POLUSDT": 1.0,
    }
    return precision_map.get(symbol.upper(), 0.01)


def query_binance_tick_size(symbol: str,
                            use_testnet: bool = True) -> Optional[float]:
    """从 exchangeInfo 查询某个 symbol 的 PRICE_FILTER.tickSize"""
    info = _get_exchange_info(use_testnet)
    if not info:
        return None
    try:
        for item in info.get("symbols", []):
            if item.get("symbol") == symbol:
                for f in item.get("filters", []):
                    if f.get("filterType") == "PRICE_FILTER":
                        tick_size = f.get("tickSize", "0.00000001")
                        return float(tick_size)
    except Exception as e:
        logger.warning("query_tick_size_failed symbol=%s error=%s", symbol, e)
    return None


def get_symbol_tick_size(symbol: str, use_testnet: bool = True) -> float:
    """获取交易对价格精度（tickSize），优先从 Binance 查询，失败则使用本地映射"""
    tick = query_binance_tick_size(symbol, use_testnet)
    if tick is not None:
        return tick

    tick_size_map = {
        "BTCUSDT": 0.01,
        "ETHUSDT": 0.01,
        "BNBUSDT": 0.01,
        "SOLUSDT": 0.01,
        "ADAUSDT": 0.0001,
        "DOGEUSDT": 0.0001,
        "BEATUSDT": 0.0001,
        "WIFUSDT": 0.0001,
        "POLUSDT": 0.00001,
    }
    return tick_size_map.get(symbol.upper(), 0.0001)


def format_price(price: float, symbol: str, use_testnet: bool = True) -> str:
    """
    按 Binance tickSize 格式化价格。

    返回字符串形式，调用方可根据需要再转 float。
    """
    try:
        tick_size = get_symbol_tick_size(symbol, use_testnet)

        # 计算需要的小数位数
        if tick_size >= 1:
            decimal_places = 0
        else:
            tick_size_str = str(float(tick_size))
            if "e" in tick_size_str.lower():
                import re

                match = re.search(r"e-(\d+)", tick_size_str.lower())
                if match:
                    decimal_places = int(match.group(1))
                else:
                    decimal_places = 8
            elif "." in tick_size_str:
                decimal_places = len(tick_size_str.split(".")[-1].rstrip("0"))
            else:
                decimal_places = 0

        # 根据 tickSize 调整价格（四舍五入到最近的 tickSize 倍数）
        if tick_size == 0:
            adjusted_price = price
        else:
            adjusted_price = round(price / tick_size) * tick_size

        # 按需要的小数位数格式化
        if decimal_places == 0:
            return f"{int(adjusted_price)}"
        return f"{adjusted_price:.{decimal_places}f}"
    except Exception as e:
        logger.warning("format_price_failed symbol=%s price=%s error=%s",
                       symbol, price, e)
        return str(price)


def format_quantity(
    quantity: Any,
    symbol: str,
    order_type: str = "open",
    price: float = None,
    use_testnet: bool = True,
) -> str:
    """
    按 Binance LOT_SIZE + 名义价值下限格式化数量。

    - order_type: "open" 使用 ROUND_DOWN, "close"/"reduce" 使用 ROUND_UP
    - MIN_NOTIONAL 固定为 5 USDT
    """
    try:
        step_size = get_symbol_step_size(symbol, use_testnet)
        MIN_NOTIONAL = 5.0

        if isinstance(quantity, str):
            quantity_decimal = Decimal(quantity)
        else:
            quantity_decimal = Decimal(str(float(quantity)))

        step_decimal = Decimal(str(step_size))
        step_str = str(step_size)
        decimal_places = len(
            step_str.split(".")[-1].rstrip("0")) if "." in step_str else 0

        rounding = ROUND_DOWN if order_type == "open" else ROUND_UP
        quantize_exp = Decimal("0." + "0" * (decimal_places - 1) +
                               "1") if decimal_places > 0 else Decimal("1")
        rounded_quantity = quantity_decimal.quantize(quantize_exp,
                                                     rounding=rounding)

        if step_size < 1:
            rounded_quantity = (rounded_quantity //
                                step_decimal) * step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp,
                                                         rounding=rounding)

        if rounded_quantity <= 0:
            rounded_quantity = step_decimal
            rounded_quantity = rounded_quantity.quantize(quantize_exp,
                                                         rounding=ROUND_UP)

        # 名义价值检查
        if price is not None and price > 0:
            notional_value = float(rounded_quantity) * price
            if notional_value < MIN_NOTIONAL:
                min_quantity = Decimal(str(MIN_NOTIONAL / price))
                min_quantity = (min_quantity // step_decimal +
                                Decimal("1")) * step_decimal
                min_quantity = min_quantity.quantize(quantize_exp,
                                                     rounding=ROUND_UP)
                rounded_quantity = min_quantity

        result_str = str(rounded_quantity)
        if decimal_places == 0:
            if "." in result_str:
                result_str = result_str.split(".")[0]
            return result_str

        if "." in result_str:
            integer_part, decimal_part = result_str.split(".")
            decimal_part = decimal_part.rstrip("0")
            if len(decimal_part) == 0 and decimal_places > 0:
                decimal_part = "0" * decimal_places
            elif len(decimal_part) < decimal_places:
                decimal_part = decimal_part + "0" * (decimal_places -
                                                     len(decimal_part))
            result_str = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
        else:
            if decimal_places > 0:
                result_str = result_str + "." + "0" * decimal_places

        return result_str
    except Exception as e:
        logger.warning(
            "format_quantity_failed symbol=%s quantity=%s order_type=%s price=%s error=%s",
            symbol,
            quantity,
            order_type,
            price,
            e,
        )
        return str(quantity)
