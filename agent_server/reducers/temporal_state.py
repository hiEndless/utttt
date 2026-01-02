"""
面向多信号来源
事件流 + Reducer
"""

import os
import json
import time
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from agent_server.config import settings


class TemporalStateReducer:
    def __init__(self, redis: Optional[aioredis.Redis] = None):
        self.redis = redis or aioredis.Redis(
            host=settings.redis_host,
            password=settings.redis_password,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self.stream = os.getenv("RISK_INPUT_STREAM", "risk_input_events")
        self.group = os.getenv("RISK_INPUT_GROUP", "risk_temporal_group")
        self.consumer = os.getenv("RISK_INPUT_CONSUMER", "risk_temporal_reducer")
        self.dedup_ms = int(os.getenv("RISK_TEMPORAL_DEDUP_MS", "1000"))
        self.cooldown_ms = int(os.getenv("RISK_TEMPORAL_COOLDOWN_MS", "60000"))
        self.flip_window_ms = int(os.getenv("RISK_TEMPORAL_FLIP_WINDOW_MS", "60000"))
        self.ema_alpha = float(os.getenv("RISK_TEMPORAL_EMA_ALPHA", "0.3"))
        self.latest_ttl_s = int(os.getenv("RISK_TEMPORAL_LATEST_TTL_S", "86400"))

    def _latest_key(self, exchange: str, account_id: str, symbol: str, position_side: str) -> str:
        ex = (exchange or "").lower()
        acc = (account_id or "").lower()
        sym = symbol or ""
        side = (position_side or "").upper()
        return f"risk_temporal:{ex}:{acc}:{sym}:{side}:latest"

    async def _read_json(self, key: str) -> Dict[str, Any]:
        try:
            v = await self.redis.get(key)
            return json.loads(v) if v else {}
        except Exception:
            return {}

    async def _write_json(self, key: str, obj: Dict[str, Any]) -> None:
        await self.redis.set(key, json.dumps(obj, ensure_ascii=False))
        await self.redis.expire(key, self.latest_ttl_s)

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _normalize_event(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        def _g(k: str):
            v = fields.get(k)
            if isinstance(v, (bytes, bytearray)):
                try:
                    return v.decode()
                except Exception:
                    return str(v)
            return v
        ex = _g("exchange") or ""
        acc = _g("account_id") or ""
        sym = _g("symbol") or ""
        side = _g("position_side") or _g("side") or ""
        verdict = (_g("verdict") or "").upper()
        conf = _g("confidence_numeric")
        try:
            confidence = float(conf) if conf is not None else None
        except Exception:
            confidence = None
        ts_raw = _g("ts")
        try:
            ts = int(float(ts_raw)) if ts_raw is not None else self._now_ms()
        except Exception:
            ts = self._now_ms()
        return {
            "exchange": ex,
            "account_id": acc,
            "symbol": sym,
            "position_side": side,
            "verdict": verdict,
            "confidence": confidence,
            "ts": ts,
        }

    def _update_state(self, state: Dict[str, Any], ev: Dict[str, Any]) -> Dict[str, Any]:
        ts = int(ev.get("ts") or self._now_ms())
        verdict = ev.get("verdict") or ""
        confidence = ev.get("confidence")
        last_update_ts = int(state.get("last_update_ts") or 0)
        if last_update_ts and ts - last_update_ts < self.dedup_ms:
            return state
        invalid = int(state.get("invalid_streak") or 0)
        conflict = int(state.get("conflict_streak") or 0)
        valid = int(state.get("valid_streak") or 0)
        last_verdict = state.get("last_verdict")
        last_flip_ts = int(state.get("last_flip_ts") or 0)
        flip_window_start = int(state.get("flip_window_start") or ts)
        flip_count_window = int(state.get("flip_count_window") or 0)
        entry_ts = int(state.get("entry_ts") or ts)
        ema = float(state.get("confidence_ema") or (confidence if confidence is not None else 0.0))
        prev_ema = ema
        if verdict == "INVALID":
            invalid += 1
            conflict = 0
            valid = 0
        elif verdict == "CONFLICT":
            conflict += 1
            invalid = 0
            valid = 0
        elif verdict in {"VALID", "STRONG"}:
            valid += 1
            invalid = 0
            conflict = 0
        if last_verdict and verdict and verdict != last_verdict:
            last_flip_ts = ts
            if ts - flip_window_start > self.flip_window_ms:
                flip_window_start = ts
                flip_count_window = 1
            else:
                flip_count_window += 1
        if confidence is not None:
            ema = self.ema_alpha * float(confidence) + (1.0 - self.ema_alpha) * float(prev_ema)
        holding_duration_min = max(0, int((ts - entry_ts) / 60000))
        cooldown_until = int(state.get("cooldown_until") or 0)
        if invalid >= 1 and verdict == "INVALID":
            cooldown_until = max(cooldown_until, ts + self.cooldown_ms)
        confidence_trend = "flat"
        if confidence is not None:
            if float(confidence) > prev_ema:
                confidence_trend = "up"
            elif float(confidence) < prev_ema:
                confidence_trend = "down"
        out = dict(state or {})
        out.update({
            "holding_duration_min": holding_duration_min,
            "last_verdict": verdict or last_verdict or "",
            "invalid_streak": invalid,
            "conflict_streak": conflict,
            "valid_streak": valid,
            "last_update_ts": ts,
            "last_flip_ts": last_flip_ts,
            "flip_window_start": flip_window_start,
            "flip_count_window": flip_count_window,
            "confidence_ema": ema,
            "confidence_trend": confidence_trend,
            "cooldown_until": cooldown_until,
            "entry_ts": entry_ts,
        })
        return out

    async def run(self):
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception:
            pass
        while True:
            res = await self.redis.xreadgroup(self.group, self.consumer, streams={self.stream: ">"}, count=50, block=5000)
            if not res:
                continue
            for _stream_name, entries in res:
                for entry_id, fields in entries:
                    ev = {k: (v if isinstance(v, str) else str(v)) for k, v in fields.items()}
                    e = self._normalize_event(ev)
                    k = self._latest_key(e.get("exchange") or "", e.get("account_id") or "", e.get("symbol") or "", e.get("position_side") or "")
                    cur = await self._read_json(k)
                    new_state = self._update_state(cur or {}, e)
                    await self._write_json(k, new_state)
                    await self.redis.xack(self.stream, self.group, entry_id)
