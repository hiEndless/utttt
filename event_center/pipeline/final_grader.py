import asyncio
import json
import os
from redis import asyncio as aioredis

from event_center.config import cfg


class FinalGrader:
    """
    Final Stage:
    - Priority gating
    - State + time debounce
    - Structure-level context packaging for downstream agents
    """

    GRADER_VERSION = "1.2.0"
    FINAL_MIN_PRIORITY = "low"  # 最低优先级，低于此优先级的事件将被忽略
    FINAL_REQUIRE_BACKGROUND = True  # 是否要求背景就绪后再推送 final（market_structure/market_state）

    PRIORITY_WEIGHT = {
        "low": 10,
        "medium": 50,
        "high": 80,
        "critical": 100,
    }

    TF_HINTS = {
        "short": ["1m", "5m"],
        "mid": ["15m", "30m", "1h"],
        "long": ["2h", "4h", "1d"],
    }

    def __init__(self, redis_url: str = cfg.redis_url):
        self.redis = aioredis.from_url(redis_url)
        self._load_scripts()

    def _load_scripts(self):
        # Atomic: state change + time window debounce
        self.check_script = self.redis.register_script("""
            local state_key = KEYS[1]
            local lock_key = KEYS[2]
            local new_state = ARGV[1]
            local new_ts = tonumber(ARGV[2])
            local min_int = tonumber(ARGV[3])

            local last_state = redis.call('get', state_key)
            if last_state and last_state == new_state then
                return 0
            end

            local last_lock = redis.call('get', lock_key)
            if last_lock then
                local last_ts = tonumber(last_lock)
                if last_ts > 0 and (new_ts - last_ts) < min_int then
                    return -1
                end
            end

            redis.call('set', state_key, new_state)
            redis.call('set', lock_key, new_ts)
            return 1
        """)

    @staticmethod
    def _normalize_ts_ms(ts: int) -> int:
        if ts >= 10**12:
            return ts
        return ts * 1000

    @staticmethod
    def _infer_confidence(total_score: float, market_state: str) -> str:
        if market_state == "trend" and abs(total_score) >= 3.0:
            return "high"
        if abs(total_score) >= 1.5:
            return "medium"
        return "low"

    def _tf_hint_from_bias(self, short_bias: bool, mid_bias: bool):
        if mid_bias:
            return self.TF_HINTS["mid"]
        if short_bias:
            return self.TF_HINTS["short"]
        return self.TF_HINTS["short"]

    @staticmethod
    def _dominant_bucket(short_bias: bool, mid_bias: bool) -> str:
        if short_bias and mid_bias:
            return "mixed"
        if mid_bias:
            return "mid"
        if short_bias:
            return "short"
        return "unknown"

    async def run(self):
        group = "final_group"
        consumer = "final_consumer_1"

        try:
            await self.redis.xgroup_create(cfg.l1_stream, group, id="0", mkstream=True)
        except Exception:
            pass

        min_priority = self.FINAL_MIN_PRIORITY  # 最低优先级门控
        require_bg = self.FINAL_REQUIRE_BACKGROUND  # 背景就绪开关

        while True:
            res = await self.redis.xreadgroup(
                group,
                consumer,
                streams={cfg.l1_stream: ">"},
                count=20,
                block=5000,
            )

            if not res:
                continue

            for _, entries in res:
                for entry_id, fields in entries:
                    ev = {k.decode(): v.decode() for k, v in fields.items()}

                    account = ev.get("account_id")
                    symbol = ev.get("symbol")
                    exchange = None
                    # 从 event_id 或 account_id 推断交易所
                    try:
                        se_id = ev.get("event_id") or ""
                        parts = se_id.split(".")
                        if len(parts) >= 5:
                            exchange = (parts[0] or "").lower()
                    except Exception:
                        exchange = None
                    if not exchange:
                        try:
                            acc = ev.get("account_id") or ""
                            if acc:
                                exchange = (acc.split("_")[0] or "").lower()
                        except Exception:
                            exchange = None

                    ts_raw = int(ev.get("timestamp") or "0")
                    ts_ms = self._normalize_ts_ms(ts_raw)

                    direction = ev.get("direction") or ""
                    market_state = ev.get("market_state") or ""
                    total_score = float(ev.get("total_score") or 0.0)

                    short_bias = (ev.get("short_term_bias") or "false") == "true"
                    mid_bias = (ev.get("mid_term_bias") or "false") == "true"

                    prio = ev.get("result_priority") or "low"
                    if self.PRIORITY_WEIGHT.get(prio, 0) < self.PRIORITY_WEIGHT.get(min_priority, 0):
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        continue
                    # 背景就绪检查：需同时存在 market_structure 与 market_state
                    if require_bg and exchange and symbol:
                        try:
                            k1 = f"background:{exchange}:{symbol}:market_structure"
                            k2 = f"background:{exchange}:{symbol}:market_state"
                            e1 = await self.redis.exists(k1)
                            e2 = await self.redis.exists(k2)
                        except Exception:
                            e1, e2 = 0, 0
                        if not (e1 and e2):
                            await self.redis.xack(cfg.l1_stream, group, entry_id)
                            continue

                    min_interval = 900 if mid_bias else 300

                    state_key = f"final:last_state:{account}:{symbol}"
                    lock_key = f"final:lock:{account}:{symbol}:{market_state}:{direction}"
                    full_state = f"{market_state}:{direction}"

                    try:
                        ok = await self.check_script(
                            keys=[state_key, lock_key],
                            args=[full_state, ts_ms, min_interval * 1000],
                        )
                    except Exception:
                        ok = -2

                    if ok != 1:
                        await self.redis.xack(cfg.l1_stream, group, entry_id)
                        continue

                    confidence = self._infer_confidence(total_score, market_state)
                    confidence_numeric = (
                        0.8 if confidence == "high"
                        else 0.5 if confidence == "medium"
                        else 0.2
                    )

                    dominant_bucket = self._dominant_bucket(short_bias, mid_bias)

                    supporting = []
                    if short_bias:
                        supporting.append("short")
                    if mid_bias:
                        supporting.append("mid")

                    reason_tags = []
                    if dominant_bucket == "mixed":
                        reason_tags.append("multi_tf_alignment")
                    if abs(total_score) >= 3.0:
                        reason_tags.append("high_structure_score")

                    # 解析 component_scores 和 indicator_values
                    try:
                        comp_scores = json.loads(ev.get("component_scores")) if ev.get("component_scores") else {}
                    except Exception:
                        comp_scores = {}
                    
                    try:
                        ind_values = json.loads(ev.get("indicator_values")) if ev.get("indicator_values") else []
                    except Exception:
                        ind_values = []

                    # ---------- Debug payload (agent default不读取) ----------
                    debug_payload = {
                        "scores": {
                            "bucket_short": ev.get("bucket_short_score"),
                            "bucket_mid": ev.get("bucket_mid_score"),
                            "bucket_long": ev.get("bucket_long_score"),
                        },
                        "dirs": {
                            "short": ev.get("short_dir"),
                            "mid": ev.get("mid_dir"),
                            "long": ev.get("long_dir"),
                        },
                        "component_scores": comp_scores,
                        "indicators": ind_values,
                    }

                    origin_sources = None
                    try:
                        origin_sources = json.loads(ev.get("origin_sources")) if ev.get("origin_sources") else None
                    except Exception:
                        origin_sources = None
                    origin_source_hint = ev.get("origin_source_hint") or "unknown"

                    final = {
                        "event_id": f"{symbol}.final.{ts_raw}",
                        "stage": "final",
                        "event_type": "market.structure",
                        "account_id": account,
                        "symbol": symbol,
                        "timestamp": str(ts_raw),
                        "final_priority": prio,
                        "source_category": origin_source_hint,

                        # ---- Structure (agent核心读取) ----
                        "structure": json.dumps({
                            "market_state": market_state,
                            "direction": direction,
                            "signature": f"{market_state}:{direction}",
                            "confidence": confidence,
                            "confidence_numeric": confidence_numeric,
                            "priority_weight": self.PRIORITY_WEIGHT.get(prio, 0),
                        }, ensure_ascii=False),

                        # ---- Analysis Context (结构级) ----
                        "analysis_context": json.dumps({
                            "dominant_bucket": dominant_bucket,
                            "supporting_buckets": supporting,
                            "tf_hint": self._tf_hint_from_bias(short_bias, mid_bias),
                            "l1_total_score": total_score,
                            "bias": {
                                "short": short_bias,
                                "mid": mid_bias,
                            },
                            "reason_tags": reason_tags,
                            "lock_window_sec": min_interval,
                            "provenance": {
                                "origin_sources": origin_sources,
                                "origin_source_hint": origin_source_hint,
                            },
                            "_debug": debug_payload,
                        }, ensure_ascii=False),

                        # ---- Meta ----
                        "meta": json.dumps({
                            "grader_version": self.GRADER_VERSION,
                            "source_event_id": ev.get("event_id"),
                            "ts_unit": "ms",
                            "min_interval_sec": min_interval,
                            "origin_source_hint": origin_source_hint,
                            "origin_sources": origin_sources,
                        }, ensure_ascii=False),
                    }

                    if ev.get("l0_priority"):
                        final["l0_priority"] = ev.get("l0_priority")
                    if ev.get("source_rule_id"):
                        final["source_rule_id"] = ev.get("source_rule_id")

                    await self.redis.xadd(cfg.final_stream, final)
                    await self.redis.xack(cfg.l1_stream, group, entry_id)


if __name__ == "__main__":
    fg = FinalGrader()
    asyncio.run(fg.run())
