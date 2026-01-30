import json
import time
import os
from data_server.binance.ws_binance.utils.redis_client import (
    get_sync_redis,
    key_ticks,
    key_latest_price,
)
from data_server.binance.ws_binance.utils.redis_batch_writer import get_batch_writer

conn = get_sync_redis()
# 使用批量写入器（减少连接使用）
batch_writer = get_batch_writer()


def update_depth(symbol, depth_data, ts=None):
    # 当前10档深度
    # key = f"depth:binance:{symbol}"
    # print(depth_data)
    # conn.set(key, json.dumps(depth_data))
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
    
    # 使用批量写入队列（解决Too many connections问题）
    # 注意：update_depth是同步函数，但它在异步上下文中被调用
    # 使用线程安全的同步批量写入器
    try:
        # 同步批量写入器使用线程安全的队列
        batch_writer.add_xadd(stream_key, payload, maxlen=1000, approximate=True)
        # 打印日志（可选，减少日志量）
        # print(f"[TOP_DEPTH] {symbol} 添加到批量队列: {payload}")
    except Exception as e:
        # 如果批量写入失败，降级到直接写入（带重试）
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn.xadd(stream_key, payload, maxlen=1000, approximate=True)
                print(f"[TOP_DEPTH] {symbol} 直接写入 {stream_key}: {payload}")
                return
            except Exception as e2:
                error_str = str(e2)
                if ("Too many connections" in error_str or "Connection" in error_str) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                if attempt == max_retries - 1:
                    print(f"[TOP_DEPTH] {symbol} Redis XADD 失败: {e2} (retried {max_retries} times)")
                return


def get_depth(symbol):
    key = f"depth:{symbol}"
    data = conn.get(key)
    if not data:
        return None
    return json.loads(data)
