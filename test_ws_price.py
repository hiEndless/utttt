import os
import time
import requests
import redis


def get_redis_client():
    """创建 Redis 同步客户端，用于读取 ws_binance 写入的最新价格。"""
    host = os.environ.get("REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("REDIS_PORT", 6379))
    db = int(os.environ.get("REDIS_DB", 1))
    password = os.environ.get("REDIS_PASSWORD", None)

    kwargs = {
        "host": host,
        "port": port,
        "db": db,
        "decode_responses": True,
    }
    if password:
        kwargs["password"] = password

    return redis.Redis(**kwargs)


def read_ws_price(symbol: str):
    """
    从 ws_binance 写入的 Redis 里读取最新价格:
    key = price:binance:{symbol}
    field: price, ts
    """
    r = get_redis_client()
    key = f"price:binance:{symbol}"
    data = r.hgetall(key)
    if not data:
        return None, None

    try:
        price = float(data.get("price"))
    except (TypeError, ValueError):
        price = None

    try:
        ts_ms = int(data.get("ts"))
    except (TypeError, ValueError):
        ts_ms = None

    return price, ts_ms


def read_binance_price(symbol: str):
    """
    调用 Binance 合约接口获取最新价格（futures price）
    """
    url = "https://fapi.binance.com/fapi/v1/ticker/price"
    resp = requests.get(url, params={"symbol": symbol}, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    return float(data["price"])


def main():
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    symbol = symbol.upper()

    print(f"测试交易对: {symbol}")

    ws_price, ws_ts = read_ws_price(symbol)
    if ws_price is None:
        print(f"[WS] Redis 中没有找到价格 key=price:binance:{symbol}")
        print("请确认：")
        print("1) ws_binance.market_ws 已启动")
        print("2) Redis 中已添加监控符号：SADD symbol:binance", symbol)
        return

    # 计算 WS 数据相对当前时间的滞后（秒）
    now = time.time()
    delay_s = None
    if ws_ts:
        delay_s = now - ws_ts / 1000

    try:
        exch_price = read_binance_price(symbol)
    except Exception as e:
        print(f"[EXCH] 获取交易所价格失败: {e}")
        return

    # 计算差异
    diff = exch_price - ws_price
    diff_pct = diff / exch_price * 100 if exch_price != 0 else 0

    print("========== 对比结果 ==========")
    if ws_ts:
        ts_readable = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(ws_ts / 1000)
        )
        print(
            f"[WS]   price: {ws_price:.8f}  ts(ms): {ws_ts}  ts_readable: {ts_readable}"
        )
        if delay_s is not None:
            print(f"[WS]   数据滞后: {delay_s:.3f} 秒（当前时间与 ts 的差值）")
    else:
        print(f"[WS]   price: {ws_price:.8f}  ts: <None>")

    print(f"[EXCH] price: {exch_price:.8f}")
    print(f"差值: {diff:.8f} ({diff_pct:.6f}%)")
    print("==============================")


if __name__ == "__main__":
    main()

