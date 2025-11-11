import redis
import json
import os
import time


class RedisClient:
    def __init__(self,
                 host=None,
                 port=None,
                 password=None,
                 db=None,):

        self.conn = redis.Redis(
            host=host or os.environ.get("REDIS_HOST", "127.0.0.1"),
            port=port or int(os.environ.get("REDIS_PORT", 6379)),
            password=password or os.environ.get("REDIS_PASSWORD", None),
            db=db or int(os.environ.get("REDIS_DB", 1)),
            decode_responses=True,
        )

    # ========== 通用 set/get ==========
    def set_json(self, key: str, value):
        """自动 JSON 序列化存储"""
        self.conn.set(key, json.dumps(value))

    def get_json(self, key: str):
        """自动 JSON 反序列化读取"""
        data = self.conn.get(key)
        if not data:
            return None
        return json.loads(data)

    def set_raw(self, key: str, value: str):
        """普通字符串 set"""
        self.conn.set(key, value)

    def get_raw(self, key: str):
        return self.conn.get(key)

    def set_hash(self, key: str, mapping_dict: dict, check_type: bool = True):
        """存储哈希类型。默认检查现有键类型，非 hash 则删除避免 WRONGTYPE。
        Args:
            key: Redis 键名
            mapping_dict: 要写入的字段字典
            check_type: 是否检查并处理现有键类型
        """
        try:
            if check_type:
                ktype = self.conn.type(key)
                if ktype and ktype != "hash":
                    if ktype != "none":
                        self.conn.delete(key)
            self.conn.hset(key, mapping=mapping_dict)
        except Exception as e:
            try:
                ktype = self.conn.type(key)
            except Exception:
                ktype = "unknown"
            print(f"Redis HSET error on key={key} type={ktype}: {e}")

    def get_hash(self, key: str):
        """读取整个哈希。若键不是 hash 或不存在，则返回 None。"""
        try:
            ktype = self.conn.type(key)
            if ktype != "hash":
                return None
            return self.conn.hgetall(key)
        except Exception as e:
            print(f"Redis HGETALL error on key={key}: {e}")
            return None

    # ========== depth 专用 API ==========
    def update_depth(self, symbol: str, depth_data: dict, ts: int = None):
        """
        depth_data:
        {
            "bids": [["price1","qty1"], ...],
            "asks": [["price1","qty1"], ...]
        }
        """
        key = f"depth:binance:{symbol}"
        self.set_json(key, depth_data)

        # 同步计算 Top10 聚合指标
        # 若 ts 未提供，使用当前时间戳（毫秒整数）
        if ts is None:
            ts = int(time.time()*1000)
        self._update_top_depth(symbol, depth_data, ts)

    def _update_top_depth(self, symbol: str, depth_data: dict, ts: int = None, top_n: int = 10):
        """
        聚合深度信息，存到 ticks:binance:{symbol} 最新值
        加固内容：
        - 安全的浮点数转换
        - 数据验证与过滤
        - 统一字符串化写入
        - 详细日志输出
        """
        bids_raw = depth_data.get("bids", [])
        asks_raw = depth_data.get("asks", [])

        # 基础校验：必须为可迭代的列表
        if not isinstance(bids_raw, list) or not isinstance(asks_raw, list):
            print(f"[TOP_DEPTH] {symbol} bids/asks 不是列表，跳过。")
            return

        # 仅保留前 top_n
        bids_raw = bids_raw[:top_n]
        asks_raw = asks_raw[:top_n]

        if not bids_raw or not asks_raw:
            print(f"[TOP_DEPTH] {symbol} bids/asks 空，跳过。")
            return

        def safe_parse_pair(pair):
            """安全解析 [price, qty]，返回 (price_f, qty_f) 或 None。"""
            try:
                if (
                    isinstance(pair, (list, tuple)) and len(pair) == 2 and
                    pair[0] is not None and pair[1] is not None
                ):
                    pf = float(pair[0])
                    qf = float(pair[1])
                    # 过滤 NaN/Inf
                    if not (pf == pf and qf == qf):  # NaN 检查
                        return None
                    if pf in (float('inf'), float('-inf')) or qf in (float('inf'), float('-inf')):
                        return None
                    return pf, qf
            except Exception:
                return None
            return None

        # 过滤与安全解析
        bids = [safe_parse_pair(p) for p in bids_raw]
        asks = [safe_parse_pair(p) for p in asks_raw]
        bids = [x for x in bids if x is not None]
        asks = [x for x in asks if x is not None]

        if not bids or not asks:
            print(f"[TOP_DEPTH] {symbol} 有无效价格对，过滤后为空，跳过。原始 bids={bids_raw} asks={asks_raw}")
            return

        # 计算最优价与数量和
        try:
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            bid_qty_sum = sum(b[1] for b in bids)
            ask_qty_sum = sum(a[1] for a in asks)
        except Exception as e:
            print(f"[TOP_DEPTH] {symbol} 计算最优价/数量失败：{e}")
            return

        # # 加权平均价（除零保护）
        # try:
        #     bid_depth_weighted = sum(b[0] * b[1] for b in bids) / max(bid_qty_sum, 1e-9)
        #     ask_depth_weighted = sum(a[0] * a[1] for a in asks) / max(ask_qty_sum, 1e-9)
        # except Exception as e:
        #     print(f"[TOP_DEPTH] {symbol} 计算加权均价失败：{e}")
        #     return

        # 统一字段命名：bid/ask 与 ticks 流保持一致，并尽量补齐 price
        # 优先从最新价格哈希读取；没有则使用中间价
        latest_key = f"price:binance:{symbol}"
        price_val = None
        try:
            pv = self.conn.hget(latest_key, "price")
            if pv is not None:
                price_val = float(pv)
        except Exception:
            price_val = None
        if price_val is None:
            try:
                price_val = (best_bid + best_ask) / 2.0
            except Exception:
                price_val = best_bid

        top_depth_summary = {
            "ts": ts,
            "price": price_val,
            "bid": bid_qty_sum,
            "ask": ask_qty_sum
        }

        # 存到 Redis Stream，保留历史
        stream_key = f"ticks:binance:{symbol}"
        # 统一字符串化（避免空字段），但确保 ts 为毫秒整数字符串
        payload = {k: (str(int(v)) if k == "ts" else str(v)) for k, v in top_depth_summary.items()}
        try:
            self.conn.xadd(stream_key, payload, maxlen=1000, approximate=True)
            print(f"[TOP_DEPTH] {symbol} 写入 {stream_key}: {payload}")
        except Exception as e:
            print(f"[TOP_DEPTH] {symbol} Redis XADD 失败: {e}. payload={payload}")

    def get_depth(self, symbol: str):
        key = f"depth:{symbol}"
        return self.get_json(key)


if __name__ == "__main__":
    rc = RedisClient()
    # 使用集合类型：先删除旧键，避免类型不匹配
    # rc.conn.delete("symbol:binance")
    rc.conn.sadd("symbol:binance", "BTCUSDT")
    print(rc.conn.smembers("symbol:binance"))