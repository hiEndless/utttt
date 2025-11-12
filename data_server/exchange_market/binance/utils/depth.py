import json
import time
import os
from data_server.exchange_market.binance.utils.redis_client import (
    get_sync_redis,
    key_ticks,
    key_latest_price,
)

conn = get_sync_redis()


def update_depth(symbol, depth_data, ts=None):
    key = f"depth:binance:{symbol}"
    print(depth_data)
    conn.set(key, json.dumps(depth_data))
    if ts is None:
        ts = int(time.time() * 1000)
    _update_top_depth(symbol, depth_data, ts)


def _update_top_depth(symbol, depth_data, ts=None, top_n=10):
    bids_raw = depth_data.get("bids", [])
    asks_raw = depth_data.get("asks", [])

    if not isinstance(bids_raw, list) or not isinstance(asks_raw, list):
        print(f"[TOP_DEPTH] {symbol} bids/asks 不是列表，跳过。")
        return

    bids_raw = bids_raw[:top_n]
    asks_raw = asks_raw[:top_n]

    if not bids_raw or not asks_raw:
        print(f"[TOP_DEPTH] {symbol} bids/asks 空，跳过。")
        return

    def safe_parse_pair(pair):
        try:
            if (
                isinstance(pair, (list, tuple))
                and len(pair) == 2
                and pair[0] is not None
                and pair[1] is not None
            ):
                pf = float(pair[0])
                qf = float(pair[1])
                if not (pf == pf and qf == qf):
                    return None
                if pf in (float("inf"), float("-inf")) or qf in (
                    float("inf"),
                    float("-inf"),
                ):
                    return None
                return pf, qf
        except Exception:
            return None
        return None

    bids = [safe_parse_pair(p) for p in bids_raw]
    asks = [safe_parse_pair(p) for p in asks_raw]
    bids = [x for x in bids if x is not None]
    asks = [x for x in asks if x is not None]

    if not bids or not asks:
        print(
            f"[TOP_DEPTH] {symbol} 有无效价格对，过滤后为空，跳过。原始 bids={bids_raw} asks={asks_raw}"
        )
        return

    try:
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        bid_qty_sum = sum(b[1] for b in bids)
        ask_qty_sum = sum(a[1] for a in asks)
    except Exception as e:
        print(f"[TOP_DEPTH] {symbol} 计算最优价/数量失败：{e}")
        return

    latest_key = key_latest_price(symbol)
    price_val = None
    try:
        pv = conn.hget(latest_key, "price")
        if pv is not None:
            price_val = float(pv)
    except Exception:
        price_val = None
    if price_val is None:
        try:
            price_val = (best_bid + best_ask) / 2.0
        except Exception:
            price_val = best_bid

    top_depth_summary = {"ts": ts, "price": price_val, "bid": bid_qty_sum, "ask": ask_qty_sum}

    stream_key = key_ticks(symbol)
    payload = {k: (str(int(v)) if k == "ts" else str(v)) for k, v in top_depth_summary.items()}
    try:
        conn.xadd(stream_key, payload, maxlen=1000, approximate=True)
        print(f"[TOP_DEPTH] {symbol} 写入 {stream_key}: {payload}")
    except Exception as e:
        print(f"[TOP_DEPTH] {symbol} Redis XADD 失败: {e}. payload={payload}")


def get_depth(symbol):
    key = f"depth:{symbol}"
    data = conn.get(key)
    if not data:
        return None
    return json.loads(data)
