import asyncio
import json
import time
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from event_center.config import cfg
import os
import yaml


class L1Aggregator:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis_url = redis_url
        self.redis = aioredis.from_url(redis_url)
        self.neutral_band = 2.0
        self.bucket_band_map = {"short": 0.6, "mid": 0.8, "long": 1.2}
        self.short_boost = 0.2
        self.mid_boost = 0.3
        self.window_seconds = 300
        self.window_count = 10
        self.class_map = self._load_class_map()
        
    async def _reconnect(self) -> None:
        # Redis 短暂断连时重建连接，避免整个后台退出
        try:
            if getattr(self, "redis", None):
                await self.redis.aclose()
        except Exception:
            pass
        self.redis = aioredis.from_url(self.redis_url)

    def _load_class_map(self):
        try:
            base_dir = os.path.dirname(__file__)
            cfg_dir = os.path.join(base_dir, "indicators_event", "config")
            with open(os.path.join(cfg_dir, "indicator_class_map.yaml"), "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _infer_cls(self, plugin_name: str):
        m = self.class_map or {}
        by_plug = (m.get("by_plugin") or {})
        for cls, names in by_plug.items():
            if isinstance(names, list) and str(plugin_name or "").lower() in [n.lower() for n in names]:
                return cls
        # fallback by keyword
        n = str(plugin_name or "").lower()
        for kw, cls in [
            ("macd", "trend"),
            ("ema", "trend"),
            ("ma", "trend"),
            ("boll", "volatility"),
            ("williams", "momentum"),
            ("rsi", "momentum"),
            ("kdj", "momentum"),
            ("atr", "volatility"),
        ]:
            if kw in n:
                return cls
        return "unknown"

    def _bucket_of_tf(self, tf: str) -> str:
        tf = str(tf or "").lower()
        if tf in ("1m", "5m"):
            return "short"
        if tf in ("15m", "30m", "1h"):
            return "mid"
        if tf in ("2h", "4h", "1d"):
            return "long"
        return "short"

    def _infer_bucket(self, primary_tf: str) -> str:
        if primary_tf:
            return self._bucket_of_tf(primary_tf)
        return "short"

    async def _update_and_fetch_window(self, symbol: str, bucket: str, item: dict):
        key = f"l1:win:{symbol}:{bucket}"
        ts_ms = int(item.get("ts") or int(time.time() * 1000))
        member = str(ts_ms)
        hkey = f"{key}:{member}"
        
        # Optimize 1: Atomic update
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {member: ts_ms})
                pipe.hset(hkey, mapping={
                    "ts": str(ts_ms),
                    "plugin": str(item.get("plugin") or ""),
                    "cls": str(item.get("cls") or ""),
                    "dir": str(item.get("dir") or ""),
                    "score": str(item.get("score") or 0.0),
                    "bucket": bucket,
                    "priority": str(item.get("priority") or "low"),
                    "source": str(item.get("source") or ""),
                })
                pipe.expire(hkey, self.window_seconds * 10)
                await pipe.execute()
        except Exception:
            pass
            
        cutoff = ts_ms - self.window_seconds * 1000
        
        # Optimize 2: Batch cleanup
        try:
            olds = await self.redis.zrangebyscore(key, min=0, max=cutoff)
            if olds:
                async with self.redis.pipeline(transaction=False) as pipe:
                    for m in olds:
                        try:
                            m_str = m.decode() if isinstance(m, (bytes, bytearray)) else m
                            pipe.delete(f"{key}:{m_str}")
                        except Exception:
                            pass
                    pipe.zremrangebyscore(key, 0, cutoff)
                    await pipe.execute()
            else:
                await self.redis.zremrangebyscore(key, 0, cutoff)
        except Exception:
            pass
            
        # Optimize 3: Batch fetch
        try:
            entries = await self.redis.zrevrange(key, 0, self.window_count - 1)
        except Exception:
            entries = []
            
        if not entries:
            return []
            
        out = []
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                for m in entries:
                    m_str = m.decode() if isinstance(m, (bytes, bytearray)) else m
                    pipe.hgetall(f"{key}:{m_str}")
                results = await pipe.execute()
                
                for obj_raw in results:
                    if not obj_raw:
                        continue
                    obj = {k.decode(): v.decode() for k, v in obj_raw.items()}
                    ts_v = int(obj.get("ts") or "0")
                    cls_v = str(obj.get("cls") or "")
                    dir_v = str(obj.get("dir") or "")
                    try:
                        sc_v = float(obj.get("score") or "0")
                    except Exception:
                        sc_v = 0.0
                    bkt = str(obj.get("bucket") or bucket)
                    prio = str(obj.get("priority") or "low")
                    src_v = str(obj.get("source") or "")
                    if ts_v >= cutoff:
                        out.append({"ts": ts_v, "plugin": obj.get("plugin"), "cls": cls_v, "dir": dir_v, "score": sc_v, "bucket": bkt, "priority": prio, "source": src_v})
        except Exception:
            pass
            
        out.sort(key=lambda x: int(x.get("ts") or 0))
        return out

    async def _fetch_all_buckets(self, symbol: str):
        items = []
        try:
            now_ms = int(time.time() * 1000)
        except Exception:
            now_ms = int(time.time() * 1000)
        cutoff = now_ms - self.window_seconds * 1000
        for b in ("short", "mid", "long"):
            try:
                key = f"l1:win:{symbol}:{b}"
                members = await self.redis.zrevrange(key, 0, self.window_count - 1)
                if not members:
                    continue
                    
                async with self.redis.pipeline(transaction=False) as pipe:
                    for m in members:
                        m_str = m.decode() if isinstance(m, (bytes, bytearray)) else m
                        pipe.hgetall(f"{key}:{m_str}")
                    results = await pipe.execute()
                    
                    for obj_raw in results:
                        if not obj_raw:
                            continue
                        obj = {k.decode(): v.decode() for k, v in obj_raw.items()}
                        try:
                            ts_val = int(obj.get("ts") or "0")
                            if ts_val < cutoff:
                                continue
                            items.append({
                                "ts": ts_val,
                                "plugin": obj.get("plugin"),
                                "cls": obj.get("cls"),
                                "dir": obj.get("dir"),
                                "score": float(obj.get("score") or "0"),
                                "bucket": b,
                                "priority": obj.get("priority") or "low",
                                "source": obj.get("source") or "",
                            })
                        except Exception:
                            continue
            except Exception:
                continue
        items.sort(key=lambda x: x.get("ts", 0))
        return items

    def _aggregate_structure(self, items: list):
        if not items:
            return {"direction": "neutral", "total_score": 0.0, "market_state": "range", "short_term_bias": False, "mid_term_bias": False}
        
        # Priority Weights
        PRIO_MULTIPLIER = {
            "low": 1.0,
            "medium": 1.2,
            "high": 1.5,
            "critical": 2.0
        }
        
        # 按结构分桶聚合
        bucket_sums = {"short": 0.0, "mid": 0.0, "long": 0.0}
        neutral_medium_presence = {"short": False, "mid": False, "long": False}
        sources_set = set()
        
        # 新增：组件分数与指标明细
        component_scores = {}
        indicator_values = []
        
        for i in items:
            d = str(i.get("dir") or "")
            b = str(i.get("bucket") or "short")
            p = str(i.get("priority") or "low").lower()
            s = str(i.get("source") or "")
            cls = str(i.get("cls") or "unknown")
            sc = float(i.get("score") or 0.0)
            
            # 记录明细
            indicator_values.append({
                "plugin": i.get("plugin"),
                "cls": cls,
                "dir": d,
                "score": sc,
                "bucket": b,
                "priority": p
            })

            if s:
                sources_set.add(s)
            
            if d == "neutral":
                if p in ("medium", "high", "critical"):
                    neutral_medium_presence[b] = True
                # 中性事件不参与分数与方向投票
                continue
                
            weight = PRIO_MULTIPLIER.get(p, 1.0)
            final_score = sc * weight
            
            signed = final_score if d == "bullish" else (-final_score if d == "bearish" else 0.0)
            if b in bucket_sums:
                bucket_sums[b] += signed
            
            # 累加组件分数
            component_scores[cls] = component_scores.get(cls, 0.0) + signed
                
        # 桶方向判定（带桶中性带）
        def dir_of(val: float, band: float):
            if abs(val) < band:
                return "neutral"
            return "bullish" if val > 0 else "bearish"
        short_dir = dir_of(bucket_sums["short"], self.bucket_band_map.get("short", 0.6))
        mid_dir = dir_of(bucket_sums["mid"], self.bucket_band_map.get("mid", 0.8))
        long_dir = dir_of(bucket_sums["long"], self.bucket_band_map.get("long", 1.2))
        total = bucket_sums["short"] + bucket_sums["mid"] + bucket_sums["long"]
        direction = "neutral" if abs(total) < self.neutral_band else ("bullish" if total > 0 else "bearish")
        # 结构状态判定：严格依据桶一致性
        if direction == "neutral":
            state = "range"
        else:
            if short_dir != "neutral" and mid_dir == short_dir:
                state = "trend"
            elif short_dir != "neutral" and mid_dir == "neutral":
                state = "momentum"
            else:
                # 其他情况（例如long主导或多桶不相邻同向），归为momentum以避免误判
                state = "momentum"
        if state == "trend" and (neutral_medium_presence["short"] or neutral_medium_presence["mid"]):
            state = "momentum"
        short_bias = short_dir != "neutral"
        mid_bias = mid_dir != "neutral"
        def _src_hint(srcs: set) -> str:
            if not srcs:
                return "unknown"
            m = []
            for s in srcs:
                if "indicators_event_generator" in s:
                    m.append("indicators")
                elif "ind_event_engine" in s:
                    m.append("indicators")
                elif "alerts_consumer" in s:
                    m.append("orderbook")
                elif "force_stats_consumer" in s:
                    m.append("liquidation")
                else:
                    m.append(s)
            u = sorted(set(m))
            if len(u) == 1:
                return u[0]
            return "mixed"
        return {
            "direction": direction,
            "total_score": total,
            "market_state": state,
            "short_term_bias": short_bias,
            "mid_term_bias": mid_bias,
            "short_dir": short_dir,
            "mid_dir": mid_dir,
            "long_dir": long_dir,
            "bucket_short_score": bucket_sums["short"],
            "bucket_mid_score": bucket_sums["mid"],
            "bucket_long_score": bucket_sums["long"],
            "component_scores": component_scores,
            "indicator_values": indicator_values,
            "origin_sources": sorted(list(sources_set)),
            "origin_source_hint": _src_hint(sources_set),
        }

    async def process_l0_event(self, entry_id, data):
        event = data
        symbol = event.get("symbol")
        etype = event.get("type") or event.get("event_type") or ""
        payload = event.get("payload") or {}
        raw = payload.get("raw") or {}
        l0 = payload.get("l0") or {}
        direction = str(l0.get("l0_direction") or raw.get("direction") or "").lower()
        score = float(l0.get("l0_score") or raw.get("signal_strength") or 0.0)
        cls = self._infer_cls(etype)
        # 统一使用毫秒时间戳，避免窗口尺度与顺序漂移
        try:
            ts_ms = int(event.get("timestamp") or "0")
        except Exception:
            ts_ms = 0
        ts = ts_ms if ts_ms else int(time.time() * 1000)
        primary_tf = str(raw.get("primary_tf") or "")
        bucket = self._infer_bucket(primary_tf)
        prio = str(event.get("priority") or "low")
        win_item = {"ts": ts, "plugin": etype, "cls": cls, "dir": direction, "score": score, "bucket": bucket, "priority": prio, "source": event.get("source") or ""}
        await self._update_and_fetch_window(symbol, bucket, win_item)
        items = await self._fetch_all_buckets(symbol)
        agg = self._aggregate_structure(items)
        pr = "high" if agg["market_state"] == "trend" else ("medium" if agg["market_state"] == "range" else "low")
        l1 = {
            "event_id": event.get("event_id"),
            "account_id": event.get("account_id"),
            "symbol": symbol,
            "stage": "l1",
            "timestamp": ts,
            "direction": agg["direction"],
            "total_score": agg["total_score"],
            "market_state": agg["market_state"],
            "short_term_bias": str(agg["short_term_bias"]).lower(),
            "mid_term_bias": str(agg["mid_term_bias"]).lower(),
            "result_priority": pr,
            "short_dir": str(agg.get("short_dir") or "").lower(),
            "mid_dir": str(agg.get("mid_dir") or "").lower(),
            "long_dir": str(agg.get("long_dir") or "").lower(),
            "bucket_short_score": agg.get("bucket_short_score") or 0.0,
            "bucket_mid_score": agg.get("bucket_mid_score") or 0.0,
            "bucket_long_score": agg.get("bucket_long_score") or 0.0,
            "component_scores": json.dumps(agg.get("component_scores") or {}),
            "indicator_values": json.dumps(agg.get("indicator_values") or []),
            "origin_sources": json.dumps(agg.get("origin_sources") or []),
            "origin_source_hint": agg.get("origin_source_hint") or "unknown",
        }
        l1 = {k: ("" if v is None else v) for k, v in l1.items()}
        try:
            await self.redis.xadd(cfg.l1_stream, l1)
        except Exception as e:
            raise e
        try:
            last_key = f"l1:last:{event.get('account_id')}:{symbol}"
            await self.redis.hset(last_key, mapping={
                "direction": agg["direction"],
                "market_state": agg["market_state"],
                "timestamp": str(ts),
                "short_term_bias": str(agg["short_term_bias"]).lower(),
                "mid_term_bias": str(agg["mid_term_bias"]).lower(),
                "result_priority": pr,
            })
        except Exception:
            pass
        print(f"[L1] 输出 symbol={symbol} 状态={agg['market_state']} 方向={agg['direction']} 分数={agg['total_score']} 优先级={pr}")

    async def run(self):
        group = "l1_group"
        consumer = "l1_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.l0_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[L1] 启动 输入流={cfg.l0_stream} 输出流={cfg.l1_stream} 消费组={group}")
        while True:
            try:
                res = await self.redis.xreadgroup(
                    group,
                    consumer,
                    streams={cfg.l0_stream: ">"},
                    count=20,
                    block=5000,
                )
            except RedisConnectionError as e:
                print(f"[L1] redis断连，重连并继续：{e}")
                await asyncio.sleep(1)
                await self._reconnect()
                try:
                    await self.redis.xgroup_create(cfg.l0_stream, group, id="0", mkstream=True)
                except Exception:
                    pass
                continue
            except Exception as e:
                print(f"[L1] xreadgroup错误，稍后重试：{e}")
                await asyncio.sleep(0.5)
                continue
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}
                    if "payload" in ev:
                        try:
                            ev["payload"] = json.loads(ev["payload"])
                        except Exception:
                            ev["payload"] = {}
                    try:
                        print(f"[L1] 读入 entry_id={entry_id.decode()} 类型={ev.get('type')} 账户={ev.get('account_id')}")
                        await self.process_l0_event(entry_id.decode(), ev)
                        await self.redis.xack(cfg.l0_stream, group, entry_id)
                        print(f"[L1] 确认 entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[L1] 错误 entry_id={entry_id.decode()} 错误={e}")


if __name__ == "__main__":
    la = L1Aggregator()
    asyncio.run(la.run())
