"""
对比 Redis 中 price:binance:{symbol} 与 Binance 合约 REST 价格。

- Redis：由 market_ws 的 REST 任务写入（约 0.8s 间隔），取 /fapi/v1/trades?limit=1 的第一条（最新一笔成交价），
  与页面「最新成交」一致。ts 为交易所该笔成交时间（ms）。正常时「数据滞后」应 ≤ 约 1 秒。
- 若滞后很大：说明 Redis 未持续更新，请重启 market_ws 并确认 REST 任务正常。
- 校验：Redis 价应与「最近 5 笔成交」的第一条一致或非常接近。
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
    从 Redis 读取 price:binance:{symbol}（Hash: price, ts）。
    由 market_ws 用 /fapi/v1/trades 第一条（最新成交）写入；ts 为交易所该笔成交时间 ms。
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


def _rest_base_url():
    """与 market_ws 一致：按 BINANCE_TESTNET 选择 REST 根地址。"""
    use_testnet = os.environ.get("BINANCE_TESTNET", "true").strip().lower() in ("1", "true", "yes", "on")
    return "https://testnet.binancefuture.com" if use_testnet else "https://fapi.binance.com"


def read_binance_ticker_price(symbol: str):
    """REST: 合约最新价（/fapi/v1/ticker/price），与写入 Redis 的 market_ws 同源。"""
    url = f"{_rest_base_url()}/fapi/v1/ticker/price"
    resp = requests.get(url, params={"symbol": symbol}, timeout=5)
    resp.raise_for_status()
    return float(resp.json()["price"])


def read_binance_last_trades(symbol: str, limit: int = 5):
    """REST: 合约最近几笔成交（/fapi/v1/trades），供参考。"""
    url = f"{_rest_base_url()}/fapi/v1/trades"
    resp = requests.get(url, params={"symbol": symbol, "limit": limit}, timeout=5)
    resp.raise_for_status()
    return resp.json()


def read_binance_mark_price(symbol: str):
    """REST: 合约标记价格（/fapi/v1/premiumIndex）。"""
    url = f"{_rest_base_url()}/fapi/v1/premiumIndex"
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
        print(f"[Redis] 中没有找到 key=price:binance:{symbol}")
        print("请确认：1) market_ws 已启动（REST ticker 任务会写入）  2) redis-cli SADD symbol:binance", symbol)
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
        base = _rest_base_url()
        print("========== 数据来源说明 ==========")
        print("[Redis] price:binance:{symbol} = market_ws 用 /fapi/v1/trades 第一条（最新一笔成交）写入（约 0.8s）")
        print(f"[EXCH]  REST = {base}：最近 5 笔成交的第一条=最新成交价，与页面一致")
        print("正常时 Redis 与「最近 5 笔成交」第一条一致，滞后 ≤ 约 1 秒。")
        print()

    print("========== 对比结果 ==========")
    if ws_ts:
        ts_readable = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ws_ts / 1000))
        print(f"[Redis] price: {ws_price:.4f}   ts(ms): {ws_ts}  该笔成交时间: {ts_readable}")
        if delay_s is not None:
            print(f"[Redis] 数据滞后: {delay_s:.2f} 秒（本机 now - 该笔成交时间，正常应 ≤ 约 1s）")
            if delay_s > 120:
                print("       ⚠ 滞后>2分钟：Redis 未持续更新，请重启 market_ws、确认 REST 任务正常。")
            elif delay_s > 5:
                print("       提示: 滞后>5秒说明未及时更新，请重启 market_ws。")
    else:
        print(f"[Redis] price: {ws_price:.4f}   ts: <None>")

    print(f"[EXCH] ticker/price(最新价): {ticker_price:.4f}  markPrice(标记价): {mark_price:.4f}")
    print(f"[EXCH] 最近 {len(last_trade_prices)} 笔成交价(第一条=最新): {[round(p, 4) for p in last_trade_prices]}")

    # Redis 存的是「最新一笔成交」，应与最近 5 笔的第一条一致
    if last_trade_prices and ws_price is not None:
        first_trade_price = last_trade_prices[0]
        diff_first = ws_price - first_trade_price
        if abs(diff_first) < 0.01:
            print("[校验] Redis 与最近一笔成交(第一条)一致，更新正常。")
        else:
            print(f"[校验] Redis 与最近一笔成交(第一条)差值: {diff_first:.4f}")
    print(f"差值( ticker - Redis ): {diff_ticker:.4f} ({diff_pct:.4f}%)")
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

