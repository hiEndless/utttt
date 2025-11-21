import json
import time
from typing import Any, Dict, List, Optional

from api.application.common.redis_client import redis_client


def _key(trade_id: str, suffix: str) -> str:
    return f"memory:{trade_id}:{suffix}"


class MemoryStore:
    async def log_event(self, trade_id: str, obj: Dict[str, Any]) -> None:
        k = _key(trade_id, "events")
        payload = {"data": json.dumps(obj, ensure_ascii=False), "ts": str(int(time.time()))}
        await redis_client.xadd(k, payload)

    async def set_latest_summary(self, trade_id: str, text: str) -> None:
        k = _key(trade_id, "latest_summary")
        await redis_client.set(k, text)

    async def get_latest_summary(self, trade_id: str) -> Optional[str]:
        k = _key(trade_id, "latest_summary")
        v = await redis_client.get(k)
        return v if v else None

    async def set_state(self, trade_id: str, patch: Dict[str, Any]) -> None:
        k = _key(trade_id, "state")
        cur = await redis_client.get(k)
        try:
            base = json.loads(cur or "{}")
        except Exception:
            base = {}
        base.update(patch or {})
        base["updated_at"] = int(time.time())
        ver = int(base.get("version") or 0) + 1
        base["version"] = ver
        await redis_client.set(k, json.dumps(base, ensure_ascii=False))

    async def get_state(self, trade_id: str) -> Dict[str, Any]:
        k = _key(trade_id, "state")
        v = await redis_client.get(k)
        try:
            return json.loads(v or "{}")
        except Exception:
            return {}

    async def set_context_slices(self, trade_id: str, slices: List[Dict[str, Any]]) -> None:
        k = _key(trade_id, "context_slices")
        data = slices[:5] if slices else []
        await redis_client.set(k, json.dumps(data, ensure_ascii=False))

    async def get_context_slices(self, trade_id: str) -> List[Dict[str, Any]]:
        k = _key(trade_id, "context_slices")
        v = await redis_client.get(k)
        try:
            obj = json.loads(v or "[]")
        except Exception:
            obj = []
        return obj if isinstance(obj, list) else []

    async def get_model_context(self, trade_id: str) -> Dict[str, Any]:
        s = await self.get_latest_summary(trade_id)
        st = await self.get_state(trade_id)
        cs = await self.get_context_slices(trade_id)
        return {"latest_summary": s or "", "state": st, "context_slices": cs}

    async def assemble_prompt(self, trade_id: str, current_event: Dict[str, Any]) -> str:
        ctx = await self.get_model_context(trade_id)
        parts = []
        parts.append("latest_summary:\n" + (ctx.get("latest_summary") or ""))
        parts.append("state:\n" + json.dumps(ctx.get("state") or {}, ensure_ascii=False))
        parts.append("context_slices:\n" + json.dumps(ctx.get("context_slices") or [], ensure_ascii=False))
        parts.append("current_event:\n" + json.dumps(current_event or {}, ensure_ascii=False))
        return "\n\n".join(parts)


class MemoryCoordinator:
    def _build_summary(self, fused: Any, weights: Dict[str, float], reflection: Dict[str, Any], event_payload: Dict[str, Any]) -> str:
        if isinstance(fused, str):
            base = fused[:1000]
        else:
            try:
                base = json.dumps(fused, ensure_ascii=False)[:1000]
            except Exception:
                base = ""
        try:
            rs = reflection.get("reflection_scores") or {}
            conf = sum(float(x) for x in rs.values()) / float(max(1, len(rs)))
        except Exception:
            conf = 0.0
        ws = {k: round(float(weights.get(k, 0.0)), 3) for k in weights.keys()}
        trend = "unknown"
        driver = "unknown"
        regime = "unknown"
        risks: List[str] = []
        try:
            sig = event_payload.get("signals") or {}
            if isinstance(sig, dict):
                if float(sig.get("RSI_5m") or 0) >= 65:
                    trend = "weak_bullish"
                if sig.get("MACD_5m") == "bullish_cross":
                    driver = "momentum_recovery"
        except Exception:
            pass
        try:
            if float(event_payload.get("funding_rate", 0)) > 0.1:
                risks.append("funding_rate_rising")
        except Exception:
            pass
        obj = {
            "current_trend_bias": trend,
            "main_driver": driver,
            "risk_factors": risks,
            "confidence": round(conf, 3),
            "market_regime": regime,
            "key_uncertainty": "unknown",
            "weights": ws,
            "summary_hint": base[:400],
        }
        return json.dumps(obj, ensure_ascii=False)

    def _build_state_patch(self, summary_text: str, prev: Dict[str, Any], reflection: Dict[str, Any], event_payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sobj = json.loads(summary_text or "{}")
        except Exception:
            sobj = {}
        conf_prev = float(prev.get("confidence") or 0.0)
        conf_new = float(sobj.get("confidence") or 0.0)
        conf_delta = conf_new - conf_prev
        trend = sobj.get("current_trend_bias") or prev.get("trend_state") or "unknown"
        driver = sobj.get("main_driver") or prev.get("driver_state") or "unknown"
        label = sobj.get("market_regime") or prev.get("market_label") or "unknown"
        risks = sobj.get("risk_factors") or []
        invalids: List[str] = []
        try:
            if float(event_payload.get("funding_rate", 0)) > 0.15:
                invalids.append("funding_rate_6h > 0.15%")
        except Exception:
            pass
        return {
            "trend_state": trend,
            "risk_state": "elevated" if risks else prev.get("risk_state", "unknown"),
            "driver_state": driver,
            "market_label": label,
            "confidence": conf_new,
            "confidence_change": round(conf_delta, 3),
            "position_thesis": (sobj.get("summary_hint") or "")[:160],
            "invalid_conditions": invalids,
        }

    def _build_slices(self, outputs: List[str]) -> List[Dict[str, Any]]:
        scored: List[Dict[str, Any]] = []
        for i, t in enumerate(outputs):
            score = 0.0
            title = f"analysis_{i}"
            reason = ""
            try:
                o = json.loads(t)
                m = o.get("metrics") or {}
                score = float(m.get("auto_score") or 0.0)
                c = o.get("content") or {}
                reason = (c.get("summary") or "")[:160]
                title = o.get("agent") or title
            except Exception:
                reason = t[:160]
            scored.append({"event_id": i, "title": title, "impact": "", "reason": reason, "score": score})
        scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return [{"event_id": x["event_id"], "title": x["title"], "impact": x["impact"], "reason": x["reason"], "link": ""} for x in scored[:5]]

    async def update(self, trade_id: str, fused: Any, outputs: List[str], reflection: Dict[str, Any], weights: Dict[str, float], event_payload: Dict[str, Any]) -> None:
        store = MemoryStore()
        await store.log_event(trade_id, {"type": "a2a_analysis", "payload": event_payload, "outputs": outputs, "reflection": reflection, "fusion": fused, "weights": weights})
        summary = self._build_summary(fused, weights, reflection, event_payload)
        await store.set_latest_summary(trade_id, summary)
        prev_state = await store.get_state(trade_id)
        patch = self._build_state_patch(summary, prev_state, reflection, event_payload)
        await store.set_state(trade_id, patch)
        slices = self._build_slices(outputs)
        await store.set_context_slices(trade_id, slices)