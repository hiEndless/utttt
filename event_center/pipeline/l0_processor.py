import asyncio
import json
import uuid
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError

from event_center.config import cfg


class L0Processor:
    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis_url = redis_url
        self.redis = aioredis.from_url(redis_url)
        self.default_priority = "low"
        self.window_seconds = 300
        self.window_count = 5
        self.min_score = 2.0
        self.high_score = 3.0
        self.consistency_ratio = 0.6
        
    async def _reconnect(self) -> None:
        # Redis 短暂断连时重建连接，避免整个后台退出
        try:
            if getattr(self, "redis", None):
                await self.redis.aclose()
        except Exception:
            pass
        self.redis = aioredis.from_url(self.redis_url)

    def tf_rank(self, tf: str) -> int:
        order = {"1m": 1, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "2h": 6, "4h": 7, "1d": 8}
        return order.get(str(tf or ""), 99)

    async def _update_and_fetch_window(self, symbol: str, plugin: str, tf: str, ts_ms: int, direction: str, strength: float):
        key = f"l0:win:{symbol}:{plugin}:{tf}"
        member = f"{ts_ms}:{uuid.uuid4().hex[:6]}"
        hkey = f"{key}:{member}"
        
        # Optimize 1: Atomic update with pipeline
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {member: ts_ms})
                pipe.hset(hkey, mapping={"ts": str(ts_ms), "dir": str(direction or ""), "score": str(strength)})
                # Safety expiration
                pipe.expire(hkey, self.window_seconds * 10)
                await pipe.execute()
        except Exception:
            pass
            
        win_sec = int(self.window_seconds)
        cutoff = ts_ms - win_sec * 1000
        
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
        win_cnt = int(self.window_count)
        try:
            members = await self.redis.zrevrange(key, 0, win_cnt - 1)
        except Exception:
            members = []
            
        if not members:
            return []

        out = []
        # Use pipeline to fetch all hashes at once
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                decoded_members = []
                for m in members:
                    m_str = m.decode() if isinstance(m, (bytes, bytearray)) else m
                    decoded_members.append(m_str)
                    pipe.hgetall(f"{key}:{m_str}")
                
                results = await pipe.execute()
                
                for i, obj_raw in enumerate(results):
                    if not obj_raw: 
                        continue
                    obj = {k.decode(): v.decode() for k, v in obj_raw.items()}
                    ts_v = int(obj.get("ts") or "0")
                    dir_v = str(obj.get("dir") or "")
                    try:
                        sc_v = float(obj.get("score") or "0")
                    except Exception:
                        sc_v = 0.0
                    
                    if ts_v >= cutoff:
                        out.append({"ts": ts_v, "dir": dir_v, "score": sc_v})
        except Exception:
            pass
            
        # sort ascending by ts
        out.sort(key=lambda x: x.get("ts", 0))
        return out

    def _confirm_signal(self, window_items: list):
        if not window_items:
            return {"l0_direction": "neutral", "l0_score": 0.0, "consistency_ratio": 0.0, "avg_abs_score": 0.0, "flip_count": 0, "neutral_reasons": ["empty_window"], "violated_min_ratio": False, "violated_min_score": False}
        dirs = [i.get("dir") for i in window_items if i.get("dir") in ("bullish", "bearish")]
        scores = [abs(float(i.get("score") or 0.0)) for i in window_items]
        avg_abs = sum(scores) / max(1, len(scores))
        bull = sum(1 for d in dirs if d == "bullish")
        bear = sum(1 for d in dirs if d == "bearish")
        total = bull + bear
        majority = "bullish" if bull >= bear else "bearish"
        ratio = (bull if majority == "bullish" else bear) / max(1, total)
        # count flips
        flips = 0
        prev = None
        for d in dirs:
            if prev is not None and d != prev:
                flips += 1
            prev = d
        min_score = float(self.min_score)
        min_ratio = float(self.consistency_ratio)
        # base direction
        l0_dir = majority if ratio >= min_ratio else "neutral"
        # base score
        l0_score = avg_abs
        neutral_reasons = []
        violated_min_ratio = ratio < min_ratio
        violated_min_score = avg_abs < min_score
        if violated_min_ratio:
            neutral_reasons.append("low_consistency")
        if flips >= 2:
            l0_score *= 0.6
            neutral_reasons.append("flip_penalty")
        # threshold gating
        if violated_min_score:
            neutral_reasons.append("low_strength")
        if l0_dir == "neutral" or violated_min_score:
            l0_dir = "neutral"
        return {
            "l0_direction": l0_dir,
            "l0_score": l0_score,
            "consistency_ratio": ratio,
            "avg_abs_score": avg_abs,
            "flip_count": flips,
            "window_count": len(window_items),
            "neutral_reasons": neutral_reasons,
            "violated_min_ratio": violated_min_ratio,
            "violated_min_score": violated_min_score,
            "directional": l0_dir != "neutral",
            "signal_type": ("non_directional" if l0_dir == "neutral" else "directional"),
        }

    async def process_msg(self, entry_id, data: dict):
        event = data
        etype = str(event.get("event_type") or event.get("type") or "")
        if etype.startswith("meta_"):
            return
        priority = self.default_priority
        matched_rules = []
        # 解析载荷（支持字符串）
        # support RES v1.0
        payload_s = event.get("payload")
        try:
            payload = json.loads(payload_s) if isinstance(payload_s, str) else (payload_s or {})
        except Exception:
            payload = {"raw": payload_s}
        # 取引擎摘要作为RAW输入
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        raw_dir = str(summary.get("direction") or "").lower()
        try:
            src = str(event.get("source") or "")
            et = str(event.get("event_type") or event.get("type") or "")
            if src == "force_stats_consumer" and et.startswith("force_"):
                et_l = et.lower()
                if "sell" in et_l:
                    raw_dir = "bearish"
                elif "buy" in et_l:
                    raw_dir = "bullish"
                elif "intensity" in et_l:
                    details = payload.get("details") or {}
                    try:
                        d_sell = float(details.get("delta_sell", 0.0)) + float(details.get("delta_sell_qty", 0.0))
                        d_buy = float(details.get("delta_buy", 0.0)) + float(details.get("delta_buy_qty", 0.0))
                        raw_dir = "bullish" if d_buy >= d_sell else "bearish"
                    except Exception:
                        pass
        except Exception:
            pass
        raw_strength = float(summary.get("signal_strength") or 0.0)
        symbol = event.get("symbol") or ""
        evidence_plugins = []
        try:
            evd = payload.get("evidence") or {}
            evidence_plugins = evd.get("plugins") or []
        except Exception:
            evidence_plugins = []
        if evidence_plugins:
            try:
                plugin = "+".join(sorted([str(p.get("name")) for p in evidence_plugins if p.get("name")]))
            except Exception:
                plugin = etype or ""
        else:
            plugin = etype or ""
        tfs = []
        try:
            for p in evidence_plugins:
                tfs.extend(p.get("tfs") or [])
        except Exception:
            pass
        tf = (min(tfs, key=self.tf_rank) if tfs else "unknown")
        try:
            ts_ms = int(event.get("timestamp") or "0")
        except Exception:
            ts_ms = 0
        # 更新窗口并确认信号
        window_items = await self._update_and_fetch_window(symbol, plugin, tf, ts_ms, raw_dir, raw_strength)
        confirm = self._confirm_signal(window_items)
        # 映射priority
        high_thr = float(self.high_score)
        if confirm["l0_direction"] == "neutral":
            if confirm.get("violated_min_ratio"):
                priority = "low"
            elif confirm.get("l0_score", 0.0) >= high_thr:
                priority = "medium"
            elif confirm.get("violated_min_score"):
                priority = "low"
            elif confirm.get("l0_score", 0.0) >= float(self.min_score):
                priority = "medium"
            else:
                priority = "low"
        else:
            if confirm["l0_score"] >= high_thr:
                priority = "high"
            elif confirm["l0_score"] >= float(self.min_score):
                priority = "medium"
            else:
                priority = "low"

        try:
            lvl = int(event.get("event_level") or 0)
        except Exception:
            lvl = 0

        l0 = {
            "event_id": event.get("event_id"),
            "timestamp": event.get("timestamp"),
            "account_id": event.get("account_id"),
            "symbol": event.get("symbol"),
            "stage": "l0",
            "event_class": event.get("event_class") or event.get("class") or "",
            "event_type": event.get("event_type") or event.get("type") or "",
            "type": event.get("event_type") or event.get("type") or "",
            "source": event.get("source"),
            "event_level": lvl,
            "payload": json.dumps({
                "raw": summary,
                "l0": confirm,
            }, ensure_ascii=False),
            "priority": priority,
            "matched_rules": json.dumps(matched_rules),
        }
        l0 = {k: ("" if v is None else v) for k, v in l0.items()}
        await self.redis.xadd(cfg.l0_stream, l0)
        print(f"[L0] 输出 event_id={l0.get('event_id')} 优先级={priority} 信号={confirm}")

    async def run(self):
        group = "l0_group"
        consumer = "l0_consumer_1"
        try:
            await self.redis.xgroup_create(cfg.raw_stream, group, id="0", mkstream=True)
        except Exception:
            pass
        print(f"[L0] 启动 原始流={cfg.raw_stream} 输出流={cfg.l0_stream} 消费组={group}")
        while True:
            try:
                res = await self.redis.xreadgroup(
                    group,
                    consumer,
                    streams={cfg.raw_stream: ">"},
                    count=10,
                    block=5000,
                )
            except RedisConnectionError as e:
                print(f"[L0] redis断连，重连并继续：{e}")
                await asyncio.sleep(1)
                await self._reconnect()
                # Redis 重启后消费组可能消失，尝试重建
                try:
                    await self.redis.xgroup_create(cfg.raw_stream, group, id="0", mkstream=True)
                except Exception:
                    pass
                continue
            except Exception as e:
                print(f"[L0] xreadgroup错误，稍后重试：{e}")
                await asyncio.sleep(0.5)
                continue
            if not res:
                continue
            for stream_name, entries in res:
                for entry_id, fields in entries:
                    raw = None
                    if b"data" in fields:
                        try:
                            raw = json.loads(fields[b"data"].decode())
                        except Exception:
                            raw = {}
                    else:
                        raw = {k.decode(): v.decode() for k, v in fields.items()}
                        if "payload" in raw:
                            try:
                                raw["payload"] = json.loads(raw["payload"])
                            except Exception:
                                pass
                    try:
                        print(f"[L0] 读入 entry_id={entry_id.decode()} 字段={list(raw.keys())}")
                        await self.process_msg(entry_id.decode(), raw)
                        await self.redis.xack(cfg.raw_stream, group, entry_id)
                        print(f"[L0] 确认 entry_id={entry_id.decode()}")
                    except Exception as e:
                        print(f"[L0] 错误 entry_id={entry_id.decode()} 错误={e}")


if __name__ == "__main__":
    lp = L0Processor()
    asyncio.run(lp.run())
