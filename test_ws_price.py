"""
对比 Redis 中 price:binance:{symbol} 与 Binance 合约 REST 价格。

- 数据源：WS 与 REST 均为同一市场（wss://fstream.binance.com + https://fapi.binance.com，USDT 永续），接口无误。
- Redis：来自 market_ws 的 aggTrade 最新一笔成交价 (msg["p"])，ts 为交易所该笔成交时间 msg["T"]（ms）。
- 若「数据滞后」持续增大（如 200s→300s）、且 Redis 里 ts 一直是一小段旧时间：
  说明 Redis 未持续更新，可能 (1) market_ws 断线/未写入  (2) 本机时间比交易所快很多。
  请：同步服务器时间（NTP），并确认 market_ws 常驻、连的是 fstream.binance.com。
- 滞后计算用本机 time.time()，本机时间不准会导致滞后显示偏大或偏小。
"""
import os
import time
import requests
import redis


def get_redis_client():
    """创建 Redis 同步客户端，与 market_ws 使用相同 REDIS_HOST/PORT/DB。"""
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
    从 market_ws 写入的 Redis 读取: key=price:binance:{symbol}, field: price, ts.
    price 来自 WebSocket aggTrade 的 msg["p"], ts 来自 msg["T"]（该笔成交时间 ms）。
    """
    r = get_redis_client()
    key = f"price:binance:{symbol}"
    data = r.hgetall(key)
    if not data:
        return None, None

    p = data.get("price")
    try:
        price = float(p) if p is not None and str(p).strip() else None
    except (TypeError, ValueError):
        price = None

    t = data.get("ts")
    try:
        ts_ms = int(float(t)) if t is not None and str(t).strip() else None
    except (TypeError, ValueError):
        ts_ms = None

    if price is None:
        return None, None
    return price, ts_ms


def read_binance_ticker_price(symbol: str):
    """REST: 合约最新价（/fapi/v1/ticker/price）。"""
    url = "https://fapi.binance.com/fapi/v1/ticker/price"
    resp = requests.get(url, params={"symbol": symbol}, timeout=5)
    resp.raise_for_status()
    return float(resp.json()["price"])


def read_binance_last_trades(symbol: str, limit: int = 5):
    """REST: 合约最近几笔成交（/fapi/v1/trades），用于交叉验证 Redis 价格是否来自真实成交。"""
    url = "https://fapi.binance.com/fapi/v1/trades"
    resp = requests.get(url, params={"symbol": symbol, "limit": limit}, timeout=5)
    resp.raise_for_status()
    return resp.json()


def read_binance_mark_price(symbol: str):
    """REST: 合约标记价格（/fapi/v1/premiumIndex），用于与「当前市场价格」对比。"""
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    resp = requests.get(url, params={"symbol": symbol}, timeout=5)
    resp.raise_for_status()
    return float(resp.json()["markPrice"])


def run_once(symbol: str, verbose_header: bool = True):
    """执行一次对比，返回是否成功（Redis 有数据且交易所请求成功）。"""
    if verbose_header:
        print(f"测试交易对: {symbol}（Binance USDT 永续合约）")
        print()

    ws_price, ws_ts = read_ws_price(symbol)
    if ws_price is None:
        print(f"[WS] Redis 中没有找到 key=price:binance:{symbol}")
        print("请确认：1) market_ws 已启动  2) redis-cli SADD symbol:binance", symbol)
        return False

    now = time.time()
    delay_s = (now - ws_ts / 1000) if ws_ts else None

    try:
        ticker_price = read_binance_ticker_price(symbol)
        mark_price = read_binance_mark_price(symbol)
        trades = read_binance_last_trades(symbol, limit=5)
    except Exception as e:
        print(f"[EXCH] 获取交易所数据失败: {e}")
        return False

    # 合约 REST /fapi/v1/trades 返回字段为 "price"（字符串），非 "p"
    last_trade_prices = []
    for t in trades:
        p = t.get("price") or t.get("p")
        if p is not None:
            try:
                last_trade_prices.append(float(p))
            except (TypeError, ValueError):
                pass
    diff_ticker = ticker_price - ws_price
    diff_pct = diff_ticker / ticker_price * 100 if ticker_price else 0

    if verbose_header:
        print("========== 数据来源说明 ==========")
        print("[WS]   Redis = market_ws 写入的 aggTrade 最新一笔成交价 (wss://fstream.binance.com)")
        print("[EXCH] REST = 当前市场价格 (https://fapi.binance.com)：ticker/price=最新价，markPrice=标记价")
        print("同一市场；若滞后持续增大、Redis 里 ts 一直是一小段旧时间，说明数据未持续更新，请查 NTP 与 market_ws 连接。")
        print()

    print("========== 对比结果 ==========")
    if ws_ts:
        ts_readable = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ws_ts / 1000))
        print(f"[WS]   price: {ws_price:.4f}   ts(ms): {ws_ts}  时间: {ts_readable}")
        if delay_s is not None:
            print(f"[WS]   数据滞后: {delay_s:.2f} 秒（本机 now - 该笔成交时间）")
            if delay_s > 120:
                print("       ⚠ 滞后>2分钟：Redis 可能未持续更新，请检查 (1) 服务器时间 NTP 同步  (2) market_ws 是否常驻并连接 fstream.binance.com")
            elif delay_s > 5:
                print("       提示: 滞后>5秒时，与当前价差几十属正常；或检查本机时间是否与网络同步。")
    else:
        print(f"[WS]   price: {ws_price:.4f}   ts: <None>")

    print(f"[EXCH] ticker/price(最新价): {ticker_price:.4f}  markPrice(标记价): {mark_price:.4f}")
    print(f"[EXCH] 最近 {len(last_trade_prices)} 笔成交价: {[round(p, 4) for p in last_trade_prices]}")

    # Redis 价格应等于「最近成交」中的某一笔（或非常接近），说明写入无误
    if last_trade_prices and ws_price is not None:
        min_dist = min(abs(ws_price - p) for p in last_trade_prices)
        if min_dist < 0.01:
            print("[校验] Redis 价格与交易所最近成交中的一笔一致（误差<0.01），写入正确。")
        else:
            print(f"[校验] Redis 与最近几笔成交最小差: {min_dist:.4f}（滞后大时可能都不在最近 5 笔内，属正常）")
    elif not last_trade_prices:
        print("[校验] 未获取到最近成交，跳过校验。")

    print(f"差值( ticker - ws ): {diff_ticker:.4f} ({diff_pct:.4f}%)")
    print("================================")
    return True


def main():
    import sys

    argv = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    symbol = (argv[0] if argv else "BTCUSDT").upper()
    loop = "--loop" in sys.argv or "-l" in sys.argv
    interval = 3
    for a in sys.argv[1:]:
        if a == "--interval" and sys.argv[sys.argv.index(a) + 1:]:
            try:
                interval = float(sys.argv[sys.argv.index(a) + 1])
            except (ValueError, IndexError):
                pass
            break

    if loop:
        print(f"持续分析 {symbol}，每 {interval} 秒刷新，Ctrl+C 退出")
        print()
        first = True
        while True:
            if not first:
                print()
            run_once(symbol, verbose_header=first)
            first = False
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n已停止")
                break
    else:
        run_once(symbol)


if __name__ == "__main__":
    main()

